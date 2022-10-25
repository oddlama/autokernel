use super::{Bridge, SymbolSetError, SymbolValue};

use anyhow::{ensure, Result};
use colored::Colorize;

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
    pub error: Option<SymbolSetError>,
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
    // TODO extract source line and display like rustc
    // hide stacktrace unless --verbose / --debug is given
    let mut n_errors = 0u32;
    for (i, t) in history.iter().enumerate() {
        if let Some(error) = &t.error {
            n_errors += 1;
            eprintln!(
                "{}: failed to assign symbol {} to {:?} at this location...",
                "error".red().bold(),
                &t.symbol,
                &t.value
            );
            print_location(t);
            print_value_change_note(t);
            eprint!("{}: ", "note".green());
            match error {
                SymbolSetError::UnmetDependencies { min: _, max: _, deps } => {
                    eprintln!("...because it currently has unmet dependencies");
                    for dep in deps {
                        eprintln!("   {} {}", "|".blue(), dep)
                    }
                    eprintln!("{}: did you mean to also set these symbols?", "note".green());
                }
                _ => eprintln!("{}", error)
            }
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

    ensure!(n_errors == 0, "aborting due to {} previous errors", n_errors);
    Ok(())
}
