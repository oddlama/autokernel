use std::collections::{HashSet, VecDeque};

use super::types::SymbolType;
use super::{expr::Terminal, Expr};
use super::{Bridge, Symbol, Tristate};
use thiserror::Error;

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
}

#[derive(Debug, Clone)]
pub struct Assignment {
    pub symbol: String,
    pub value: Tristate,
}

pub trait Solver {
    fn satisfy(&self, bridge: &Bridge, expr: &Expr, desired_value: Tristate) -> Result<Vec<Assignment>, SolveError>;
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

pub fn satisfy(bridge: &Bridge, symbol: String, config: SolverConfig) -> Result<Vec<Assignment>, SolveError> {
    if config.recursive {
        let mut queue = VecDeque::new();
        queue.push_back(symbol);

        let mut requirements = Vec::new();
        let mut done = HashSet::new();
        while let Some(symbol) = queue.pop_front() {
            // Skip symbols that were already satisfied
            if !done.insert(symbol.clone()) {
                continue;
            }

            let expr = bridge
                .symbol(&symbol)
                .ok_or(SolveError::InvalidSymbol)?
                .direct_dependencies()
                .map_err(|_| SolveError::InvalidExpression)?;

            let mut reqs = config.solver.satisfy(bridge, &expr, config.desired_value)?;
            for i in &reqs {
                if i.value != Tristate::No {
                    queue.push_back(i.symbol.clone());
                }
            }
            requirements.append(&mut reqs);
        }

        Ok(requirements)
    } else {
        let expr = bridge
            .symbol(&symbol)
            .ok_or(SolveError::InvalidSymbol)?
            .direct_dependencies()
            .map_err(|_| SolveError::InvalidExpression)?;

        config.solver.satisfy(bridge, &expr, config.desired_value)
    }
}

pub struct SimpleSolver {}
impl SimpleSolver {
    fn satisfy_eq(&self, a: &Symbol, b: Tristate) -> Result<Vec<Assignment>, SolveError> {
        let name = a.name_owned().ok_or(SolveError::InvalidSymbol)?;
        if b == Tristate::Mod && a.symbol_type() != SymbolType::Tristate {
            return Err(SolveError::RequiresModForBoolean { symbol: name });
        }

        Ok(vec![Assignment { symbol: name, value: b }])
    }

    fn satisfy_neq(&self, a: &Symbol, b: Tristate, desired_value: Tristate) -> Result<Vec<Assignment>, SolveError> {
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

        Ok(vec![Assignment {
            symbol: a.name_owned().ok_or(SolveError::InvalidSymbol)?,
            value,
        }])
    }
}

impl Solver for SimpleSolver {
    fn satisfy(&self, bridge: &Bridge, expr: &Expr, desired_value: Tristate) -> Result<Vec<Assignment>, SolveError> {
        // If the expression already evaluates to at least the desired value,
        // we don't have to change any variables
        if expr.eval().map_err(|_| SolveError::UnsupportedConstituents)? >= desired_value {
            return Ok(vec![]);
        }

        Ok(match expr {
            Expr::And(a, b) => {
                let a = self.satisfy(bridge, a, desired_value)?;
                let b = self.satisfy(bridge, b, desired_value)?;

                // TODO dont calculate conflict here, instead supply "already changed"
                // map to this function so that conflicts can be detected when genereated,
                // also then we can override get_tristate_value with this map to generate
                // a tight list from the beginning
                todo!();

                [a, b].concat()
            }
            Expr::Or(a, b) => {
                if let Ok(assignment) = self.satisfy(bridge, a, desired_value) {
                    assignment
                } else {
                    self.satisfy(bridge, b, desired_value)?
                }
            }
            Expr::Const(false) => return Err(SolveError::Unsatisfiable),
            Expr::Const(true) => vec![],
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
