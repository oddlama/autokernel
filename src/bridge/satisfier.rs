use super::types::CSymbol;
use super::{expr::Terminal, Expr};
use super::{Symbol, Tristate};
use anyhow::{bail, Context, Result};
use typed_builder::TypedBuilder;


/// Satisfier to solve symbol dependencies
///
/// ```
/// let satisfier = Satisfier::builder()
///     .bound(Tristate::Yes)
///     .recursive(true);
/// satisfier.satisfy()
/// ```
#[derive(TypedBuilder)]
pub struct Satisfier {
    #[builder(default=Box::new(SimpleSolver{}), setter(into))]
    solver: Box<dyn Solver>,
    #[builder(default=Tristate::Mod, setter(into))]
    bound: Tristate,
    #[builder(default, setter(into))]
    recursive: bool,
}
impl Satisfier {
    pub fn satisfy(&self, symbol: &Symbol) -> Result<Vec<String>> {
        let dep = symbol.direct_dependencies()?.unwrap_or(Expr::Const(true));

        if self.recursive {
            todo!("track list and satisfy the new ones");
            // TODO: error when the dependency expects ==n
        }

        self.solver.satisfy(dep)
    }
}

pub trait Solver {
    fn satisfy(&self, expr: Expr) -> Result<Vec<String>>;
}

// TODO: pass the bridge to simplify symbol access (and make it more safe)
pub struct SimpleSolver {}

impl Solver for SimpleSolver {

    fn satisfy(&self, expr: Expr) -> Result<Vec<String>> {
        Ok(match expr {
            Expr::And(a, b) => [self.satisfy(*a)?, self.satisfy(*b)?].concat(),
            Expr::Or(a, b) => {
                bail!(format!("ambiguous: please satisfy either {:?} or {:?}", a, b));
                // TODO: will we ever need this for more complex logic?
                //let sa = satisfy(*a);
                //let sb = satisfy(*b);
                //match (sa,sb) {
                //    (Ok(l1), Ok(l2)) => bail!(format!("ambiguous: please satisfy either {:?} or {:?}", l1, l2)),
                //    (Ok(l1), Err(_)) => l1,
                //    (Err(_), Ok(l2)) => l2,
                //    (Err(_), Err(_)) => bail!("unsatisfiable, both or branches"),
                //}
            }
            Expr::Const(false) => bail!("unsatisfiable: false"),
            Expr::Const(true) => vec![],
            Expr::Not(a) => match *a {
                Expr::Terminal(t) => self.satisfy_terminal(t, true)?.map_or_else(Vec::new, |el| vec![el]),
                _ => bail!("not supported"),
            },
            Expr::Terminal(t) => self.satisfy_terminal(t, false)?.map_or_else(Vec::new, |el| vec![el]),
        })
    }
}
impl SimpleSolver {
    fn symbol_to_tristate(&self, sym: *mut CSymbol) -> Option<Tristate> {
        self.name(sym).ok()?.parse().ok()
    }

    fn name(&self, sym: *mut CSymbol) -> Result<String> {
        Ok(unsafe { &*sym }.name().clone().context("unnamed symbol")?.to_string())
    }

    fn satisfy_terminal(&self, terminal: Terminal, not: bool) -> Result<Option<String>> {
        let mut terminal = terminal;
        if not {
            if let Terminal::Eq(a, b) = terminal {
                terminal = Terminal::Neq(a, b);
            }
            if let Terminal::Neq(a, b) = terminal {
                terminal = Terminal::Eq(a, b);
            }
        }

        // no mod yes symbols
        Ok(match terminal {
            Terminal::Eq(a, b) => match (self.symbol_to_tristate(a), self.symbol_to_tristate(b)) {
                (Some(t), None) => self.is_satisfied(b, t)?,
                (None, Some(t)) => self.is_satisfied(a, t)?,
                _ => bail!("not supported, not just one tristate"),
            },
            Terminal::Neq(a, b) => match (self.symbol_to_tristate(a), self.symbol_to_tristate(b)) {
                (Some(t), None) => {
                    if self.is_satisfied(b, t)?.is_none() {
                        None
                    } else {
                        bail!(format!("ambiguous, set {:?} not to {}", self.name(b), t))
                    }
                }
                (None, Some(t)) => {
                    if self.is_satisfied(a, t)?.is_none() {
                        None
                    } else {
                        bail!(format!("ambiguous, set {:?} not to {}", self.name(a), t))
                    }
                }
                _ => bail!("not supported, not just one tristate"),
            },
            Terminal::Lth(_, _) => bail!(format!("not supported {:?}", terminal)),
            Terminal::Leq(_, _) => bail!(format!("not supported {:?}", terminal)),
            Terminal::Gth(_, _) => bail!(format!("not supported {:?}", terminal)),
            Terminal::Geq(_, _) => bail!(format!("not supported {:?}", terminal)),
            Terminal::Symbol(s) => {
                self.is_satisfied(s, Tristate::Mod)?.or(self.is_satisfied(s, if not { Tristate::No } else { Tristate::Yes })?)
            }
        })
    }

    fn is_satisfied(&self, sym: *mut CSymbol, tri: Tristate) -> Result<Option<String>> {
        Ok(if unsafe { &*sym }.get_tristate_value() == tri {
            None
        } else {
            Some(self.name(sym)?)
        })
    }
}
