use super::{SymbolValue, SymbolSetError};

#[derive(Debug)]
pub enum Cause {
    Unknown
}

#[derive(Debug)]
pub struct TransactionError {
    pub cause: Cause,
    pub error: SymbolSetError,
}

#[derive(Debug)]
pub struct Transaction {
    pub symbol: String,
    pub from: String,
    pub value_before: SymbolValue,
    pub value_after: SymbolValue,
    pub error: Option<TransactionError>,
}

#[derive(Debug, Default)]
pub struct TransactionHistory {
    entries: Vec<Transaction>,
}

impl TransactionHistory {
    pub fn add(&mut self, transaction: Transaction) {
        self.entries.push(transaction);
    }
}
