use super::types::*;
use super::Bridge;
use anyhow::{bail, ensure, Result};
use std::borrow::Cow;
use std::ffi::{CStr, CString};

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

    pub fn recalculate(&self) {
        (self.bridge.vtable.c_sym_calc_value)(self.c_symbol);
    }

    pub fn get_value(&self) -> &Tristate {
        unsafe { &(*self.c_symbol).current_value.tri }
    }

    pub fn set_symbol_value(&mut self, value: SymbolValue) -> Result<()> {
        // TODO track which symbols were assigned to report conflicting later assignments.
        // TODO for choices there is no symbol name. track whether other choices were set and if
        //      they are overwritten. Tracking must have a disable switch to load external kconfig
        //      (defconfig) for example. Or a function that resets tracking state for one/all symbols.
        match value {
            SymbolValue::Auto(value) => {
                match self.symbol_type() {
                    SymbolType::Unknown => bail!(format!("TODO MESSAGE Cannot set symbol of unknown type")),
                    SymbolType::Boolean => {
                        // Allowed "y" "n"
                        ensure!(matches!(value.as_str(), "y" | "n"));
                        self.set_symbol_value(SymbolValue::Boolean(value.parse::<Tristate>().unwrap() == Tristate::Yes))?
                    }
                    SymbolType::Tristate => {
                        // Allowed "y" "m" "n"
                        self.set_symbol_value(SymbolValue::Tristate(value.parse::<Tristate>().unwrap()))?
                    }
                    SymbolType::Int => {
                        // Allowed: Any u64 integer
                        let value = value.parse::<u64>().expect("TODO MESSAGE not parsable int:");
                        self.set_symbol_value(SymbolValue::Int(value))?
                    }
                    SymbolType::Hex => {
                        // Allowed: Any u64 integer
                        ensure!(&value[2..] == "0x", format!("TODO MESSAGE must begin with 0x"));
                        let value = u64::from_str_radix(&value[2..], 16).expect("TODO MESSAGE:");
                        self.set_symbol_value(SymbolValue::Hex(value))?
                    }
                    SymbolType::String => self.set_symbol_value(SymbolValue::String(value))?,
                }
            }
            SymbolValue::Boolean(value) => {
                ensure!(self.symbol_type() == SymbolType::Boolean, "TODO no boolean");
                ensure!(!self.is_const(), "TODO const");
                let ret = (self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value.into());
                ensure!(ret == 1, format!("TODO Could not set symbol {:?}", self.name()))
            }
            SymbolValue::Tristate(value) => {
                ensure!(self.symbol_type() == SymbolType::Tristate || self.symbol_type() == SymbolType::Boolean, format!("TODO, not tristate, but {:?}", self.symbol_type()));
                ensure!(!self.is_const(), "TODO, const");
                // TODO if this is a choice, -> error
                let ret = (self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value);
                ensure!(ret == 1, format!("TODO Could not set symbol {:?}", self.name()))
            }
            SymbolValue::Int(value) => {
                ensure!(self.symbol_type() == SymbolType::Int, "TODO not int");
                ensure!(!self.is_const(), "TODO, const");
                let cstr = CString::new(value.to_string())?;
                let ret = (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr());
                ensure!(ret == 1, format!("TODO Could not set symbol {:?}", self.name()))
            }
            SymbolValue::Hex(value) => {
                ensure!(self.symbol_type() == SymbolType::Hex, "TODO not hex");
                ensure!(!self.is_const(), "TODO const");
                let cstr = CString::new(format!("0x{:x}", value))?;
                let ret = (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr());
                ensure!(ret == 1, format!("TODO Could not set symbol {:?}", self.name()))
            }
            SymbolValue::Number(value) => match self.symbol_type() {
                SymbolType::Int => self.set_symbol_value(SymbolValue::Int(value))?,
                SymbolType::Hex => self.set_symbol_value(SymbolValue::Hex(value))?,
                _ => bail!("TODO message for not parsing number"),
            },
            SymbolValue::String(value) => {
                ensure!(self.symbol_type() == SymbolType::String, "TODO not string");
                ensure!(!self.is_const(), "TODO const s");
                ensure!(!self.is_choice(), "TODO choice s");
                let cstr = CString::new(value)?;
                let ret = (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr());
                ensure!(ret == 1, format!("Could not set symbol {:?}", self.name()))
            }
        };

        // TODO check if change was successful
        self.bridge.recalculate_all_symbols();
        Ok(())
    }

    pub fn symbol_type(&self) -> SymbolType {
        unsafe { &*self.c_symbol }.symbol_type
    }

    pub fn is_const(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CONST)
    }

    pub fn is_choice(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CHOICE)
    }
}
