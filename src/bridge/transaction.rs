use super::{SymbolSetError, SymbolValue, Bridge};

use anyhow::{bail, Result};
use colored::Colorize;

#[derive(Debug)]
pub enum Cause {
    Unknown,
}

#[derive(Debug)]
pub struct TransactionError {
    pub cause: Cause,
    pub error: SymbolSetError,
}

#[derive(Debug)]
pub struct Transaction {
    /// The affected symbol
    pub symbol: String,
    /// The location (e.g. file and line numer) where the change originated from
    pub from: String,
    /// The full traceback where the change originated from
    pub traceback: Option<String>,
    /// The intended new value for the symbol
    pub value: SymbolValue,
    /// The value of the symbol before the transaction
    pub value_before: SymbolValue,
    /// The value of the symbol after the transaction
    pub value_after: SymbolValue,
    /// Any error that occurred
    pub error: Option<TransactionError>,
}

fn print_location(transaction: &Transaction) {
    eprintln!("  {} {}", "-->".blue(), transaction.from);
    if let Some(traceback) = &transaction.traceback {
        for line in traceback.lines() {
            eprintln!("   {} {}", "|".blue(), line.dimmed())
        }
    }
}

fn print_value_change_note(transaction: &Transaction) {
    if transaction.value_before == transaction.value_after {
        eprintln!(
            "   {} note: this did not change the previous value {:?}",
            "=".blue(),
            transaction.value_before
        );
    } else {
        eprintln!(
            "   {} note: this changed the value from {:?} to {:?}",
            "=".blue(),
            transaction.value_before,
            transaction.value_after
        );
    }
}

pub fn validate_transactions(bridge: &Bridge, history: &Vec<Transaction>) -> Result<()> {
    let mut n_errors = 0u32;
    for (i, t) in history.iter().enumerate() {
        if let Some(error) = &t.error {
            n_errors += 1;
            eprintln!(
                "{}: failed to assign symbol {} to {:?}",
                "error".red().bold(),
                &t.symbol,
                &t.value
            );
            print_location(t);
            print_value_change_note(t);
            let symbol = bridge.symbol(&t.symbol);
            eprintln!("TODO print nice: caused by {:?}", error);
            eprintln!("");
        }

        // Detect re-assignments
        for other in history[0..i].iter().rev() {
            if other.symbol == t.symbol {
                eprintln!(
                    "{}: reassignment of symbol {} to {:?}",
                    "warning".yellow().bold(),
                    t.symbol,
                    t.value,
                );
                print_location(t);
                print_value_change_note(t);
                eprintln!("{}: last assigned here to {:?}", "note".green(), other.value);
                print_location(other);
                print_value_change_note(other);
                eprintln!("");
                break;
            }
        }
    }

    if n_errors > 0 {
        bail!("Aborted after encountering {} errors.", n_errors);
    }

    Ok(())
}
