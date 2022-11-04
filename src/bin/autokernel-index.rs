use autokernel::bridge::{Bridge, Symbol};
use rusqlite::{Connection, Transaction};
use uuid::Uuid;

use std::io::{self, Write};
use std::path::PathBuf;
use std::process::Command;
use std::time::Instant;

use anyhow::{bail, Ok, Result, ensure, Context};
use clap::Parser;
use colored::Colorize;

#[derive(Parser, Debug)]
#[clap(version, about, long_about = None)]
struct Args {
    /// The kernel directory
    #[clap(short, long, value_name = "DIR", value_hint = clap::ValueHint::DirPath, default_value = "/usr/src/linux")]
    kernel_dir: PathBuf,

    /// The database to write to
    #[clap(short, long, value_name = "SQLITE_DB", value_hint = clap::ValueHint::FilePath, default_value = "index.db")]
    db: PathBuf,

    #[clap(subcommand)]
    action: Action,
}

#[derive(Debug, clap::Args)]
struct ActionValues {
    /// The name for this configuration
    #[clap(short, long)]
    name: String,

    /// The architecture for which the config is intended.
    #[clap(short, long, value_name = "ARCH")]
    arch: Option<String>,

    /// The kconf configuration file to apply before indexing
    #[clap(short, long, value_name = "CONFIG", value_hint = clap::ValueHint::FilePath)]
    kconf: PathBuf,
}

#[derive(Debug, clap::Subcommand)]
enum Action {
    /// Index kernel symbols, metadata and default values
    Kernel,
    /// Index symbol values
    Values(ActionValues),
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bridge = Bridge::new(args.kernel_dir.clone())?;

    let mut conn = Connection::open(&args.db)?;
    create_schema(&mut conn)?;

    let kernel_name = bridge.get_env("PWD").unwrap().split("/").last().unwrap().to_string();
    let (v_major, v_minor, v_patch) = parse_kernel_version(&bridge.get_env("KERNELVERSION").unwrap())?;

    match &args.action {
        Action::Kernel => {
            let kernel_id = Uuid::new_v4().to_string();
            let tx = conn.transaction()?;
            tx.execute(
                "INSERT INTO kernel VALUES (?1, ?2, ?3, ?4, ?5)",
                (&kernel_id, v_major, v_minor, v_patch, kernel_name),
            )?;

            index_kernel(&bridge, &tx, &kernel_id)?;
            index_values(&bridge, &tx, &kernel_id, "defaults", None, None)?;

            ensure!(Command::new("make")
                .arg("defconfig")
                .current_dir(&args.kernel_dir)
                .status()
                .context("Failed to generate defconfig")?
                .success());
            let defconfig = args.kernel_dir.join(".config");
            index_values(&bridge, &tx, &kernel_id, "defconfig", Some(&defconfig), bridge.get_env("ARCH").as_ref())?;

            tx.commit()?;
        }
        Action::Values(action) => {
            let kernel_id: String = conn
                .prepare(
                    "SELECT id from kernel WHERE version_major=? AND version_minor=? AND version_patch=? AND name=?",
                )?
                .query_row((v_major, v_minor, v_patch, &kernel_name), |row| row.get(0))?;
            let tx = conn.transaction()?;

            index_values(
                &bridge,
                &tx,
                &kernel_id,
                &action.name,
                Some(&action.kconf),
                action.arch.as_ref(),
            )?;
            tx.commit()?;
        }
    };

    Ok(())
}

fn create_schema(conn: &mut Connection) -> Result<()> {
    let tx = conn.transaction()?;
    // Create tables
    tx.execute(
        "CREATE TABLE IF NOT EXISTS kernel (
            id               TEXT NOT NULL,
            version_major    INTEGER NOT NULL,
            version_minor    INTEGER NOT NULL,
            version_patch    INTEGER NOT NULL,
            name             TEXT NOT NULL,
            UNIQUE (version_major, version_minor, version_patch, name),
            PRIMARY KEY (id))",
        (), // empty list of parameters.
    )?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS config (
            id               TEXT NOT NULL,
            kernel_id        TEXT NOT NULL REFERENCES kernel(id),
            architecture     TEXT,
            name             TEXT NOT NULL,
            UNIQUE (kernel_id, architecture, name),
            PRIMARY KEY (id))",
        (), // empty list of parameters.
    )?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS symbol (
            kernel_id        TEXT NOT NULL REFERENCES kernel(id),
            name             TEXT NOT NULL,
            type             TEXT NOT NULL,
            visibility_expression TEXT,
            reverse_dependencies  TEXT,
            PRIMARY KEY (kernel_id, name))",
        (), // empty list of parameters.
    )?;
    tx.execute(
        "CREATE TABLE IF NOT EXISTS value (
            config_id        TEXT NOT NULL REFERENCES config(id),
            symbol_name      TEXT NOT NULL,
            value            TEXT NOT NULL,
            PRIMARY KEY (config_id, symbol_name))",
        (), // empty list of parameters.
    )?;
    tx.commit()?;
    Ok(())
}

fn is_valid_symbol(symbol: &Symbol) -> bool {
    return !symbol.is_const() && symbol.name().is_some();
}

fn parse_kernel_version(ver: &str) -> Result<(u32, u32, u32)> {
    if let Some(d1) = ver.find('.') {
        let major = ver[..d1].parse::<u32>()?;
        let rest = &ver[d1 + 1..];
        if let Some(d2) = rest.find('.') {
            Ok((major, rest[..d2].parse::<u32>()?, rest[d2 + 1..].parse::<u32>()?))
        } else {
            Ok((major, rest.parse::<u32>()?, 0))
        }
    } else {
        bail!("Cannot parse kernel version (missing .)");
    }
}

fn index_kernel(bridge: &Bridge, tx: &Transaction, kernel_id: &str) -> Result<()> {
    print!("{:>12} kernel...\r", "Indexing".cyan());
    io::stdout().flush()?;

    let time_start = Instant::now();
    colored::control::set_override(false);
    let mut n_indexed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if is_valid_symbol(&symbol) {
            n_indexed_symbols += 1;

            tx.execute(
                "INSERT INTO symbol VALUES (?1, ?2, ?3, ?4, ?5)",
                (
                    kernel_id,
                    symbol.name().unwrap().to_string(),
                    symbol.symbol_type().as_ref(),
                    symbol
                        .visibility_expression_bare()
                        .unwrap()
                        .map(|e| e.display(bridge).to_string()),
                    symbol
                        .reverse_dependencies_bare()
                        .unwrap()
                        .map(|e| e.display(bridge).to_string()),
                ),
            )?;
        }
    }
    colored::control::unset_override();

    println!(
        "{:>12} kernel [{} symbols] in {:.2?}",
        "Indexed".green(),
        n_indexed_symbols,
        time_start.elapsed()
    );
    Ok(())
}

fn index_values(
    bridge: &Bridge,
    tx: &Transaction,
    kernel_id: &str,
    name: &str,
    kconf: Option<&PathBuf>,
    arch: Option<&String>,
) -> Result<()> {
    if let Some(kconf) = kconf {
        bridge.read_config_unchecked(kconf)?;
        println!("{:>12} kconf ({})", "Loaded".green(), kconf.display());
    }

    let time_start = Instant::now();
    let config_id = Uuid::new_v4().to_string();
    tx.execute(
        "INSERT INTO config VALUES (?1, ?2, ?3, ?4)",
        (&config_id, kernel_id, arch, name),
    )?;

    print!("{:>12} symbol values...\r", "Indexing".cyan());
    io::stdout().flush()?;

    let mut n_indexed_symbols = 0;
    for symbol in &bridge.symbols {
        let symbol = bridge.wrap_symbol(*symbol);
        if is_valid_symbol(&symbol) {
            n_indexed_symbols += 1;

            tx.execute(
                "INSERT INTO value VALUES (?1, ?2, ?3)",
                (
                    &config_id,
                    symbol.name().unwrap().to_string(),
                    symbol.get_string_value(),
                ),
            )?;
        }
    }

    println!(
        "{:>12} {} symbol values [{}] in {:.2?}",
        "Indexed".green(),
        n_indexed_symbols,
        name,
        time_start.elapsed()
    );
    Ok(())
}
