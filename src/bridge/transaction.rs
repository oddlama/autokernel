use crate::bridge::satisfier::{Ambiguity, SolveError};

use super::{SymbolSetError, SymbolValue, Tristate};

use anyhow::{ensure, Result};
use colored::Colorize;

#[derive(Debug)]
pub struct Transaction {
    /// The affected symbol
    pub symbol: String,
    /// The file where the change originated from
    pub file: String,
    /// The line where the change originated from
    pub line: u32,
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
    eprintln!("  {} {}:{}", "-->".blue(), transaction.file, transaction.line);
    if let Some(traceback) = &transaction.traceback {
        eprintln!("   {}", "|".blue());
        for line in traceback.lines() {
            eprintln!("   {} {}", "|".blue(), line.dimmed())
        }
        eprintln!("   {}", "|".blue());
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

fn print_satisfy_result(satisfying_configuration: &Result<Vec<(String, Tristate)>, SolveError>) {
    match satisfying_configuration {
        Ok(satisfying_configuration) => {
            eprintln!("{}: you may want to set these symbols beforehand", "note".green());
            eprintln!("   {}", "|".blue());
            for (sym, value) in satisfying_configuration {
                eprintln!(
                    "   {} {} {}",
                    "|".blue(),
                    sym,
                    format!("\"{}\"", value).color(value.color())
                )
            }
            eprintln!("   {}", "|".blue());
        }
        Err(SolveError::AmbiguousSolution { symbols }) => {
            eprintln!(
                "{}: automatic solution is ambiguous; requires manual action",
                "note".green()
            );
            for ambiguity in symbols {
                let Ambiguity { symbol, clauses } = ambiguity;
                eprintln!("   {}", "|".blue());
                eprintln!(
                    "   {} {}: one of the following expressions must be satisfied",
                    "|".blue(),
                    symbol.blue()
                );
                for clause in clauses {
                    eprintln!("   {} - {}", "|".blue(), clause)
                }
            }
            eprintln!("   {}", "|".blue());
        }
        Err(err) => eprintln!(
            "   {} note: cannot suggest solution because automatic dependency resolution failed ({:?})",
            "=".blue(),
            err
        ),
    }
}

pub fn validate_transactions(history: &Vec<Transaction>) -> Result<()> {
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
            match error {
                SymbolSetError::SatisfyFailed { error } => print_satisfy_result(&Err(error.clone())),
                SymbolSetError::UnmetDependencies {
                    min,
                    max,
                    deps,
                    satisfying_configuration,
                } => {
                    eprintln!("{}: ...because it currently has unmet dependencies", "note".green());
                    eprintln!("   {}", "|".blue());
                    for dep in deps {
                        eprintln!("   {} - {}", "|".blue(), dep)
                    }
                    eprintln!("   {}", "|".blue());
                    eprintln!(
                        "   {} note: the range of assignable values is currently [min={}, max={}]",
                        "=".blue(),
                        min.to_string().color(min.color()),
                        max.to_string().color(max.color()),
                    );
                    print_satisfy_result(satisfying_configuration);
                }
                SymbolSetError::RequiredByOther { min, max, rev_deps } => {
                    eprintln!(
                        "{}: ...because it is required by at least one other symbol",
                        "note".green()
                    );
                    eprintln!("   {}", "|".blue());
                    for dep in rev_deps {
                        eprintln!("   {} - {}", "|".blue(), dep)
                    }
                    eprintln!("   {}", "|".blue());
                    eprintln!(
                        "   {} note: the range of assignable values is currently [min={}, max={}]",
                        "=".blue(),
                        min.to_string().color(min.color()),
                        max.to_string().color(max.color()),
                    );
                }
                SymbolSetError::MustBeSelected { rev_deps } => {
                    eprintln!(
                        "{}: ...because it must be implicitly selected by satisfying any of these expressions",
                        "note".green()
                    );
                    eprintln!("   {}", "|".blue());
                    for dep in rev_deps {
                        eprintln!("   {} - {}", "|".blue(), dep)
                    }
                    eprintln!("   {}", "|".blue());
                }
                _ => eprintln!("{}", error),
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
