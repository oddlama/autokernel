use super::types::*;
use super::Bridge;
use anyhow::{ensure, Result};
use std::borrow::Cow;
use std::ffi::{CStr, CString};

#[derive(Debug, Eq, PartialEq, Ord, PartialOrd)]
#[repr(u8)]
#[allow(dead_code)]
pub enum Tristate {
    No,
    Mod,
    Yes,
}

#[derive(Debug)]
#[repr(u8)]
#[allow(dead_code)]
pub enum SymbolType {
    Unknown,
    Boolean,
    Tristate,
    Int,
    Hex,
    String,
}

pub struct Symbol<'a> {
    pub(super) c_symbol: *mut CSymbol,
    pub(super) bridge: &'a Bridge,
}

impl<'a> Symbol<'a> {
    pub fn name(&self) -> Option<Cow<'_, str>> {
        unsafe {
            (*self.c_symbol)
                .name
                .as_ref()
                .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()))
        }
    }
    // dependencies()

    pub fn recalculate(&self) {
        (self.bridge.vtable.c_sym_calc_value)(self.c_symbol);
    }

    pub fn get_value(&self) -> &Tristate {
        unsafe { &(*self.c_symbol).current_value.tri }
    }

    pub fn set_symbol_value_tristate(&mut self, value: Tristate) -> Result<()> {
        ensure!(
            (self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        self.bridge.recalculate_all_symbols();
        // TODO check if change was successful
        Ok(())
    }

    pub fn set_symbol_value_string(&mut self, value: &str) -> Result<()> {
        let cstr = CString::new(value).unwrap();
        ensure!(
            (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        self.bridge.recalculate_all_symbols();
        // TODO check if change was successful
        Ok(())
    }

    pub fn is_choice(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CHOICE)
    }

    pub fn set_symbol_value_choice(&mut self, value: &str) -> Result<()> {
        // TODO check that the given symbol belongs to the choice.
        self.bridge.symbol(value).unwrap().set_symbol_value_tristate(Tristate::Yes)?;
        self.bridge.recalculate_all_symbols();
        // TODO check if change was successful
        Ok(())
    }
}
