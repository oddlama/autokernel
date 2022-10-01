use autokernel::bridge::{Tristate, Bridge};

// TODO use test_env_logger
// TODO only download kernel once, then run many tests on it
#[test]
fn integrationtest_parse_symbols() {
    use std::env;
    use std::fs;
    use std::process::{Command, Stdio};

    let tmp = env::temp_dir().join("autokernel-test");
    println!("creating {} directory", &tmp.display());
    fs::create_dir_all(&tmp).unwrap();

    // latest="$(curl -s https://www.kernel.org/ | grep -A1 'stable:' | grep -oP '(?<=strong>).*(?=</strong.*)' | head -1)"
    let kernel_version = "linux-5.19.1";
    let kernel_tar = format!("{}.tar.xz", kernel_version);

    // remove kernel tar and folder if they already exists
    println!("cleaning previous test if exists");
    Command::new("rm").arg(&kernel_tar).current_dir(&tmp).status().unwrap();
    Command::new("rm")
        .arg("-r")
        .arg(&kernel_version)
        .current_dir(&tmp)
        .status()
        .unwrap();

    // download kernel
    println!("downloading kernel {} ...", kernel_version);
    Command::new("wget")
        .arg("-q")
        .arg(format!("https://cdn.kernel.org/pub/linux/kernel/v5.x/{}", kernel_tar))
        .current_dir(&tmp)
        .status()
        .unwrap();

    println!("extracting kernel {} ...", kernel_version);
    Command::new("tar")
        .arg("-xvf")
        .arg(&kernel_tar)
        .current_dir(&tmp)
        .stdout(Stdio::null())
        .status()
        .unwrap();

    let kernel_dir = tmp.join(kernel_version);

    println!("building and running bridge to extract all symbols");
    let bridge = Bridge::new(kernel_dir).unwrap();
    let mut sym_cmdline_bool = bridge.symbol("CMDLINE_BOOL").unwrap();
    println!("name: {}", sym_cmdline_bool.name().unwrap());
    println!("cur_val: {:?}", sym_cmdline_bool.get_value());

    sym_cmdline_bool.set_symbol_value_tristate(Tristate::Yes).unwrap();
    assert_eq!(
        *sym_cmdline_bool.get_value(),
        Tristate::Yes,
        "Setting the symbol failed"
    );

    // remove kernel tar and folder if they already exists
    println!("cleaning up");
    Command::new("rm").arg("-r").arg(&tmp).status().expect("cleanup failed");
}
