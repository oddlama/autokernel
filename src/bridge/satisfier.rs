use itertools::Itertools;
use std::collections::{HashMap, HashSet, VecDeque};

use super::types::SymbolType;
use super::{expr::Terminal, Expr};
use super::{Bridge, Symbol, Tristate};
use thiserror::Error;

pub type Assignments = HashMap<String, Tristate>;

#[derive(Debug, Clone)]
pub struct Ambiguity {
    pub symbol: String,
    pub clauses: Vec<String>,
}

#[derive(Error, Debug, Clone)]
pub enum SolveError {
    #[error("the expression is provably unsatisfiable")]
    Unsatisfiable,
    #[error("complex negated expressions are unsupported")]
    ComplexNot,
    #[error("expression contains unsupported constructs")]
    UnsupportedConstituents,
    #[error("expression contains an ambiguous comparison")]
    AmbiguousComparison,
    #[error("encountered an invalid symbol")]
    InvalidSymbol,
    #[error("encountered an invalid expression")]
    InvalidExpression,
    #[error("expression would require Tristate::Mod for boolean symbol {symbol}")]
    RequiresModForBoolean { symbol: String },
    #[error("solver yielded conflicting assignment for symbol {symbol} (both {a} and {b})")]
    ConflictingAssignment { symbol: String, a: Tristate, b: Tristate },
    #[error("solution is ambiguous, please satisfy at least one of the expressions for each symbol")]
    AmbiguousSolution { symbols: Vec<Ambiguity> },
}

pub trait Solver {
    fn satisfy(&self, bridge: &Bridge, expr: &Expr, desired_value: Tristate) -> Result<Assignments, SolveError>;
}

pub struct SolverConfig {
    pub solver: Box<dyn Solver>,
    pub desired_value: Tristate,
    pub recursive: bool,
}

impl Default for SolverConfig {
    fn default() -> Self {
        SolverConfig {
            solver: Box::new(SimpleSolver {}),
            desired_value: Tristate::Yes,
            recursive: false,
        }
    }
}

pub fn satisfy(bridge: &Bridge, symbol: String, config: SolverConfig) -> Result<Vec<(String, Tristate)>, SolveError> {
    let mut assignments: Vec<(String, Tristate)> = Vec::new();
    let mut ambiguities = Vec::new();

    // Tracks which other symbols this symbol depends on
    let mut dependencies = HashMap::<String, Vec<String>>::new();
    // symbol -> assignments
    let mut solved_symbols = HashMap::new();

    let mut done = HashSet::new();
    let mut queue = VecDeque::new();
    queue.push_back(symbol);

    while let Some(symbol) = queue.pop_front() {
        // Skip symbols that were already satisfied
        if !done.insert(symbol.clone()) {
            continue;
        }

        let bridge_symbol = bridge.symbol(&symbol).ok_or(SolveError::InvalidSymbol)?;
        let expr = bridge_symbol
            .visibility_expression()
            .map_err(|_| SolveError::InvalidExpression)?;

        // If there is no prompt, then the symbol cannot be set directly. Instead, it
        // must be implicitly selected by requiring it via the reverse_dependencies.
        // If there are several choices, we can't solve it because some options may be undesirable.
        // Yet, we don't fail in that case, because the user will notice when trying to use the partial solution,
        // and otherwise there would be no useful hint at all (but everything until then is).
        let expr = if bridge_symbol.prompt_count() == 0 {
            Expr::And(
                Box::new(expr),
                Box::new({
                    let expr = bridge_symbol
                        .reverse_dependencies_bare()
                        .map_err(|_| SolveError::InvalidExpression)?;
                    if let Some(expr) = expr {
                        let clauses = expr.or_clauses();
                        match clauses.len() {
                            // Nothing to select => assume the symbol can be trivially changed
                            0 => Expr::Const(true),
                            // Just one thing can be used to require this => Satisfy it
                            1 => clauses[0].clone(),
                            // Several possible choices exist to enable this symbol. Collect the
                            // information to later return an aggregated error. Therefore we
                            // continue with Const(true) to assume that this is already solved.
                            _ => {
                                ambiguities.push(Ambiguity {
                                    symbol: symbol.clone(),
                                    clauses: clauses.into_iter().map(|x| x.display(bridge).to_string()).collect_vec(),
                                });
                                Expr::Const(true)
                            }
                        }
                    } else {
                        // No expression attached => assume the symbol can be trivially changed
                        Expr::Const(true)
                    }
                }),
            )
        } else {
            expr
        };

        let mut new_assignments = config.solver.satisfy(bridge, &expr, config.desired_value)?;
        let depends_on: Vec<String> = new_assignments
            .iter()
            .filter(|(_, &v)| v != Tristate::No)
            .map(|(k, _)| k.clone())
            .collect();

        // Remove assignments to unassignable symbols, but only after adding
        // them to our dependencies (depends_on).
        new_assignments.retain(|k, _| bridge.symbol(k).unwrap().prompt_count() > 0);
        solved_symbols.insert(symbol.clone(), new_assignments);
        if !config.recursive {
            dependencies.insert(symbol.clone(), vec![]);
            break;
        }

        queue.extend(depends_on.iter().cloned());
        dependencies.insert(symbol.clone(), depends_on);
    }

    // Temporarily merge all assignments into a hashmap to detect collisions
    let mut merged_assignments = HashMap::new();
    for ass in solved_symbols.values() {
        merge(&mut merged_assignments, ass.clone())?;
    }

    // Now collect the assignments in the correct order, such that
    // all dependencies are set before setting the symbol itself.
    let mut already_assigned_symbols = HashSet::new();
    while !dependencies.is_empty() {
        // Split into symbols which have their dependencies fulfilled,
        // and those that still require some other symbol to be set first
        let (fulfilled_symbols, mut remaining_symbols): (HashMap<String, Vec<String>>, HashMap<String, Vec<String>>) =
            dependencies.into_iter().partition(|(_, v)| v.is_empty());

        // Collect the new assignments, but only if they weren't assigned before.
        // Conflicts cannot happen, as we already tested for conflicts before.
        for fs in fulfilled_symbols.keys() {
            solved_symbols.get_mut(fs).unwrap().drain().for_each(|e| {
                let (k, _) = &e;
                if !already_assigned_symbols.contains(k) {
                    already_assigned_symbols.insert(k.clone());
                    assignments.push(e);
                }
            });
        }

        // Remove dependencies to symbols that are now fulfilled
        for v in remaining_symbols.values_mut() {
            v.retain(|s| !fulfilled_symbols.contains_key(s))
        }
        dependencies = remaining_symbols;
    }

    if !ambiguities.is_empty() {
        return Err(SolveError::AmbiguousSolution { symbols: ambiguities });
    }

    Ok(assignments)
}

pub struct SimpleSolver {}
impl SimpleSolver {
    fn satisfy_eq(&self, a: &Symbol, b: Tristate) -> Result<Assignments, SolveError> {
        let name = a.name_owned().ok_or(SolveError::InvalidSymbol)?;
        if b == Tristate::Mod && a.symbol_type() != SymbolType::Tristate {
            return Err(SolveError::RequiresModForBoolean { symbol: name });
        }

        Ok(HashMap::from([(name, b)]))
    }

    fn satisfy_neq(&self, a: &Symbol, b: Tristate, desired_value: Tristate) -> Result<Assignments, SolveError> {
        let name = a.name_owned().ok_or(SolveError::InvalidSymbol)?;

        // a != y, des=y -> m
        // a != y, des=m -> m
        // a != m, des=y -> y
        // a != m, des=m -> y
        // a != n, des=y -> des
        // a != n, des=m -> des
        let value = match b {
            Tristate::No => desired_value,
            Tristate::Mod => Tristate::Yes,
            Tristate::Yes => Tristate::Mod,
        };

        if value == Tristate::Mod && a.symbol_type() != SymbolType::Tristate {
            return Err(SolveError::RequiresModForBoolean { symbol: name });
        }

        Ok(HashMap::from([(name, value)]))
    }
}

impl Solver for SimpleSolver {
    fn satisfy(&self, bridge: &Bridge, expr: &Expr, desired_value: Tristate) -> Result<Assignments, SolveError> {
        // If the expression already evaluates to at least the desired value,
        // we don't have to change any variables
        if expr.eval().map_err(|_| SolveError::UnsupportedConstituents)? >= desired_value {
            return Ok(HashMap::new());
        }

        Ok(match expr {
            Expr::And(a, b) => {
                let mut a = self.satisfy(bridge, a, desired_value)?;
                merge(&mut a, self.satisfy(bridge, b, desired_value)?)?;
                a
            }
            Expr::Or(a, b) => {
                if let Ok(assignment) = self.satisfy(bridge, a, desired_value) {
                    assignment
                } else {
                    self.satisfy(bridge, b, desired_value)?
                }
            }
            Expr::Const(false) => return Err(SolveError::Unsatisfiable),
            Expr::Const(true) => HashMap::new(),
            Expr::Not(a) => match &**a {
                Expr::Terminal(Terminal::Eq(a, b)) => {
                    let a = bridge.wrap_symbol(*a);
                    let b = bridge.wrap_symbol(*b);
                    if a.is_const() {
                        self.satisfy_neq(&b, a.get_tristate_value(), desired_value)?
                    } else if b.is_const() {
                        self.satisfy_neq(&a, b.get_tristate_value(), desired_value)?
                    } else {
                        return Err(SolveError::AmbiguousComparison);
                    }
                }
                Expr::Terminal(Terminal::Neq(a, b)) => {
                    let a = bridge.wrap_symbol(*a);
                    let b = bridge.wrap_symbol(*b);
                    if a.is_const() {
                        self.satisfy_eq(&b, a.get_tristate_value())?
                    } else if b.is_const() {
                        self.satisfy_eq(&a, b.get_tristate_value())?
                    } else {
                        return Err(SolveError::AmbiguousComparison);
                    }
                }
                Expr::Terminal(Terminal::Symbol(s)) => self.satisfy_eq(&bridge.wrap_symbol(*s), Tristate::No)?,
                Expr::Terminal(_) => return Err(SolveError::UnsupportedConstituents),
                _ => return Err(SolveError::ComplexNot),
            },
            Expr::Terminal(Terminal::Eq(a, b)) => {
                let a = bridge.wrap_symbol(*a);
                let b = bridge.wrap_symbol(*b);
                if a.is_const() {
                    self.satisfy_eq(&b, a.get_tristate_value())?
                } else if b.is_const() {
                    self.satisfy_eq(&a, b.get_tristate_value())?
                } else {
                    return Err(SolveError::AmbiguousComparison);
                }
            }
            Expr::Terminal(Terminal::Neq(a, b)) => {
                let a = bridge.wrap_symbol(*a);
                let b = bridge.wrap_symbol(*b);
                if a.is_const() {
                    self.satisfy_neq(&b, a.get_tristate_value(), desired_value)?
                } else if b.is_const() {
                    self.satisfy_neq(&a, b.get_tristate_value(), desired_value)?
                } else {
                    return Err(SolveError::AmbiguousComparison);
                }
            }
            Expr::Terminal(Terminal::Symbol(s)) => {
                // Almost the same as satisfy_neq(s, No), but we need to allow
                // value promotion (if desired = mod but value is a boolean, we want y instead)
                let s = bridge.wrap_symbol(*s);
                let desired_value = if s.symbol_type() == SymbolType::Boolean {
                    Tristate::Yes
                } else {
                    desired_value
                };
                self.satisfy_neq(&s, Tristate::No, desired_value)?
            }
            Expr::Terminal(_) => return Err(SolveError::UnsupportedConstituents),
        })
    }
}

fn merge(a: &mut Assignments, mut b: Assignments) -> Result<(), SolveError> {
    // Assert that there are no conflicting assignments
    let set_a: HashSet<&String> = a.keys().collect();
    let set_b: HashSet<&String> = b.keys().collect();
    for &k in set_a.intersection(&set_b) {
        let va = a[k];
        let vb = b[k];
        if va != vb {
            return Err(SolveError::ConflictingAssignment {
                symbol: k.clone(),
                a: va,
                b: vb,
            });
        }
    }

    a.extend(b.drain());
    Ok(())
}
