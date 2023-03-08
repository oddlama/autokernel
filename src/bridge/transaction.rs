use std::{
    fs::File,
    io::{BufRead, BufReader},
};

use crate::bridge::satisfier::{Ambiguity, SolveError};

use super::{SymbolSetError, SymbolValue, Tristate};

use anyhow::{ensure, Result};
use colored::{Color, Colorize};

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

fn read_line_at_location(transaction: &Transaction) -> Option<String> {
    let file = File::open(&transaction.file).ok()?;
    let line = BufReader::new(file)
        .lines()
        .nth((transaction.line - 1).try_into().unwrap())?
        .ok()?;
    Some(line)
}

struct Location<'a> {
    transaction: &'a Transaction,
    hints: &'a [&'a str],
    color: Color,
}

fn print_locations(mut locations: Vec<Location>) {
    // for line in traceback.lines() {
    //     eprintln!("   {} {}", "|".blue(), line.dimmed())
    // }
    locations.sort_by_key(|x| (&x.transaction.file, x.transaction.line));
    let num_col_width = format!("{}", locations.iter().map(|l| l.transaction.line).max().unwrap_or(0))
        .len()
        .max(2);
    let indent = " ".repeat(num_col_width);
    let mut previous_file = None;
    for loc in locations {
        if previous_file == Some(&loc.transaction.file) {
            eprintln!("{indent} {}", "|".blue());
        } else {
            eprintln!(
                "{indent}{} {}:{}",
                "-->".blue(),
                loc.transaction.file,
                loc.transaction.line
            );
            eprintln!("{indent} {}", "|".blue());
            previous_file = Some(&loc.transaction.file)
        }

        let line = read_line_at_location(loc.transaction).unwrap_or_else(|| "<cannot read file>".into());
        eprintln!(
            "{:>indent$} {} {}",
            loc.transaction.line.to_string().blue(),
            "|".blue(),
            line,
            indent = num_col_width
        );
        if !loc.hints.is_empty() {
            eprintln!(
                "{indent} {} {} {}",
                "|".blue(),
                "^".repeat(line.len()).color(loc.color),
                loc.hints[0]
            );
            for hint in loc.hints.iter().skip(1) {
                eprintln!("{indent} {} {} {}", "|".blue(), " ".repeat(line.len()), hint);
            }
        } else {
            eprint!("{indent} {} {}", "|".blue(), "^".repeat(line.len()).color(loc.color));
        }
    }
    eprintln!("{indent} {}", "|".blue());
}

fn value_change_note(transaction: &Transaction) -> String {
    if transaction.value_before == transaction.value_after {
        format!("this did not change the previous value {:?}", transaction.value_before)
    } else {
        format!(
            "this changed the value from {:?} to {:?}",
            transaction.value_before, transaction.value_after
        )
    }
}

pub fn print_satisfy_result(satisfying_configuration: &Result<Vec<(String, Tristate)>, SolveError>) {
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
        Err(SolveError::UnsupportedConstituents { description }) => {
            eprintln!(
                "   {} note: cannot derive solution because dependency expression contains unsupported constituents:",
                "=".blue()
            );
            eprintln!("   {} - {}", "|".blue(), description);
        }
        Err(err) => eprintln!(
            "   {} note: cannot suggest solution because automatic dependency resolution failed ({:?})",
            "=".blue(),
            err
        ),
    }
}

pub fn validate_transactions(history: &[Transaction]) -> Result<()> {
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

            print_locations(vec![Location {
                transaction: t,
                hints: &[&format!("hint: {}", value_change_note(t)).dimmed()],
                color: Color::Red,
            }]);
            match error {
                SymbolSetError::SatisfyFailed { error } => print_satisfy_result(&Err(error.clone())),
                SymbolSetError::UnmetDependencies {
                    min,
                    max,
                    deps,
                    satisfying_configuration,
                } => {
                    eprintln!("{}: ...because it has unmet dependencies", "note".green());
                    eprintln!("   {}", "|".blue());
                    eprintln!(
                        "   {} {}: all of the following expressions must be satisfied",
                        "|".blue(),
                        t.symbol.blue()
                    );
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
                _ => eprintln!("{}: {}", "note".green(), error),
            }
            eprintln!();
        }

        // Detect re-assignments
        for other in history[0..i].iter().rev() {
            if other.symbol == t.symbol && t.value_before != t.value_after {
                eprintln!(
                    "{}: reassignment of symbol {} to {:?}",
                    "warning".yellow().bold(),
                    t.symbol,
                    t.value,
                );
                print_locations(vec![
                    Location {
                        transaction: t,
                        hints: &[
                            &format!("help: reassigned here to {:?}", t.value).yellow(),
                            &format!("hint: {}", value_change_note(t)).dimmed(),
                        ],
                        color: Color::Yellow,
                    },
                    Location {
                        transaction: other,
                        hints: &[
                            &format!("help: previously assigned here to {:?}", t.value).yellow(),
                            &format!("hint: {}", value_change_note(t)).dimmed(),
                        ],
                        color: Color::Yellow,
                    },
                ]);
                eprintln!();
                break;
            }
        }
    }

    ensure!(n_errors == 0, "aborting due to {} previous errors", n_errors);
    Ok(())
}
