use super::types::CSymbol;
use super::Bridge;
use std::fmt;
use std::fmt::Debug;

#[derive(Debug, PartialEq, Eq, Clone)]
pub enum Terminal {
    Eq(*mut CSymbol, *mut CSymbol),
    Neq(*mut CSymbol, *mut CSymbol),
    Lth(*mut CSymbol, *mut CSymbol),
    Leq(*mut CSymbol, *mut CSymbol),
    Gth(*mut CSymbol, *mut CSymbol),
    Geq(*mut CSymbol, *mut CSymbol),
    List(),
    Symbol(*mut CSymbol),
    Range(*mut CSymbol, *mut CSymbol),
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

impl Expr {
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
            Terminal::List() => todo!(),
            Terminal::Symbol(e) => write!(f, "{}", wrap!(e)),
            Terminal::Range(_, _) => todo!(),
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