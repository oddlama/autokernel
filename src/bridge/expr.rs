use super::types::{CSymbol, SymbolType};
use super::{Bridge, Tristate};
use std::fmt;
use std::fmt::Debug;
use thiserror::Error;

#[derive(Debug, PartialEq, Eq, Clone)]
pub enum Terminal {
    Eq(*mut CSymbol, *mut CSymbol),
    Neq(*mut CSymbol, *mut CSymbol),
    Lth(*mut CSymbol, *mut CSymbol),
    Leq(*mut CSymbol, *mut CSymbol),
    Gth(*mut CSymbol, *mut CSymbol),
    Geq(*mut CSymbol, *mut CSymbol),
    Symbol(*mut CSymbol),
}

impl Terminal {
    pub fn display<'a>(&'a self, bridge: &'a Bridge) -> TerminalDisplay {
        TerminalDisplay { terminal: self, bridge }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Expr {
    Const(bool),
    Terminal(Terminal),
    And(Box<Self>, Box<Self>),
    Or(Box<Self>, Box<Self>),
    Not(Box<Self>),
}

#[derive(Error, Debug, Clone)]
pub enum EvalError {
    #[error("encountered a terminal that cannot be evaluated: {terminal:?}")]
    InvalidTerminal { terminal: Terminal },
}

impl Expr {
    pub fn or_clauses(&self) -> Vec<&Expr> {
        let mut exprs = Vec::new();
        fn visit<'a>(exprs: &mut Vec<&'a Expr>, expr: &'a Expr) {
            match expr {
                Expr::Or(a, b) => {
                    visit(exprs, a);
                    visit(exprs, b);
                }
                e => exprs.push(e),
            }
        }
        visit(&mut exprs, self);
        exprs
    }

    pub fn and_clauses(&self) -> Vec<&Expr> {
        let mut exprs = Vec::new();
        fn visit<'a>(exprs: &mut Vec<&'a Expr>, expr: &'a Expr) {
            match expr {
                Expr::And(a, b) => {
                    visit(exprs, a);
                    visit(exprs, b);
                }
                e => exprs.push(e),
            }
        }
        visit(&mut exprs, self);
        exprs
    }

    pub fn eval(&self) -> Result<Tristate, EvalError> {
        Ok(match self {
            Expr::Const(b) => (*b).into(),
            Expr::And(a, b) => {
                let a = a.eval()?;
                let b = b.eval()?;
                if a < b {
                    a
                } else {
                    b
                }
            }
            Expr::Or(a, b) => {
                let a = a.eval()?;
                let b = b.eval()?;
                if a > b {
                    a
                } else {
                    b
                }
            }
            Expr::Not(a) => a.eval()?.invert(),
            Expr::Terminal(Terminal::Eq(a, b))
                if matches!(
                    unsafe { &**a }.symbol_type(),
                    SymbolType::Tristate | SymbolType::Boolean
                ) =>
            unsafe { ((**a).get_tristate_value() == (**b).get_tristate_value()).into() },
            Expr::Terminal(Terminal::Neq(a, b))
                if matches!(
                    unsafe { &**a }.symbol_type(),
                    SymbolType::Tristate | SymbolType::Boolean
                ) =>
            unsafe { ((**a).get_tristate_value() != (**b).get_tristate_value()).into() },
            Expr::Terminal(Terminal::Symbol(s)) => unsafe { (**s).get_tristate_value() },
            Expr::Terminal(t) => return Err(EvalError::InvalidTerminal { terminal: t.clone() }),
        })
    }

    pub fn display<'a>(&'a self, bridge: &'a Bridge) -> ExprDisplay {
        ExprDisplay { expr: self, bridge }
    }
}

enum ExprType {
    And,
    Or,
    Other,
}

pub struct ExprDisplay<'a> {
    expr: &'a Expr,
    bridge: &'a Bridge,
}

pub struct TerminalDisplay<'a> {
    terminal: &'a Terminal,
    bridge: &'a Bridge,
}

impl<'a> fmt::Display for TerminalDisplay<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        macro_rules! wrap {
            ($symbol: expr) => {
                self.bridge.wrap_symbol(*$symbol)
            };
        }
        match &self.terminal {
            Terminal::Eq(l, r) => write!(f, "({} == {})", wrap!(l), wrap!(r)),
            Terminal::Neq(l, r) => write!(f, "({} != {})", wrap!(l), wrap!(r)),
            Terminal::Lth(l, r) => write!(f, "({} < {})", wrap!(l), wrap!(r)),
            Terminal::Leq(l, r) => write!(f, "({} <= {})", wrap!(l), wrap!(r)),
            Terminal::Gth(l, r) => write!(f, "({} > {})", wrap!(l), wrap!(r)),
            Terminal::Geq(l, r) => write!(f, "({} >= {})", wrap!(l), wrap!(r)),
            Terminal::Symbol(e) => write!(f, "{}", wrap!(e)),
        }
    }
}

fn display_expr(bridge: &Bridge, expr: &Expr, f: &mut fmt::Formatter<'_>, parent_type: ExprType) -> fmt::Result {
    match (parent_type, expr) {
        (ExprType::And, Expr::And(l, r)) => {
            display_expr(bridge, l, f, ExprType::And)?;
            write!(f, " && ")?;
            display_expr(bridge, r, f, ExprType::And)
        }
        (ExprType::Or, Expr::Or(l, r)) => {
            display_expr(bridge, l, f, ExprType::Or)?;
            write!(f, " || ")?;
            display_expr(bridge, r, f, ExprType::Or)
        }
        (_, Expr::And(l, r)) => {
            write!(f, "(")?;
            display_expr(bridge, l, f, ExprType::And)?;
            write!(f, " && ")?;
            display_expr(bridge, r, f, ExprType::And)?;
            write!(f, ")")
        }
        (_, Expr::Or(l, r)) => {
            write!(f, "(")?;
            display_expr(bridge, l, f, ExprType::Or)?;
            write!(f, " || ")?;
            display_expr(bridge, r, f, ExprType::Or)?;
            write!(f, ")")
        }
        (_, Expr::Not(e)) => write!(f, "!{}", e.display(bridge)),
        (_, Expr::Const(e)) => write!(f, "{}", e),
        (_, Expr::Terminal(e)) => write!(f, "{}", e.display(bridge)),
    }
}

impl<'a> fmt::Display for ExprDisplay<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        display_expr(self.bridge, self.expr, f, ExprType::Other)
    }
}
