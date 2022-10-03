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

    pub fn set_symbol_value_auto(&mut self, value: &str) -> Result<()> {
        match self.symbol_type() {
            SymbolType::Unknown => bail!(format!("TODO MESSAGE Cannot set symbol of unknown type")),
            SymbolType::Boolean => {
                // Allowed "y" "n"
                ensure!(matches!(value, "y" | "n"), "TODO: only y or n");
                self.set_symbol_value(SymbolValue::Boolean(
                    value.parse::<Tristate>().unwrap() == Tristate::Yes,
                ))
            }
            SymbolType::Tristate => {
                // Allowed "y" "m" "n"
                self.set_symbol_value(SymbolValue::Tristate(value.parse::<Tristate>().unwrap()))
            }
            SymbolType::Int => {
                // Allowed: Any u64 integer
                let value = value.parse::<u64>().expect("TODO MESSAGE not parsable int:");
                self.set_symbol_value(SymbolValue::Int(value))
            }
            SymbolType::Hex => {
                // Allowed: Any u64 integer
                ensure!(&value[..2] == "0x", format!("TODO MESSAGE must begin with 0x"));
                let value = u64::from_str_radix(&value[2..], 16).expect("TODO MESSAGE:");
                self.set_symbol_value(SymbolValue::Hex(value))
            }
            SymbolType::String => self.set_symbol_value(SymbolValue::String(value.to_owned())),
        }
    }

    pub fn set_symbol_value(&mut self, value: SymbolValue) -> Result<()> {
        // TODO track which symbols were assigned to report conflicting later assignments.
        // TODO for choices there is no symbol name. track whether other choices were set and if
        //      they are overwritten. Tracking must have a disable switch to load external kconfig
        //      (defconfig) for example. Or a function that resets tracking state for one/all symbols.
        ensure!(!self.is_const(), "TODO: Cannot assign const symbols");
        ensure!(
            !self.is_choice(),
            "TODO: Cannot assign choice symbols directly. Assign y to a choice value instead."
        );

        let set_tristate = |value: Tristate| -> Result<bool> {
            let rev_dep_tri = unsafe { (*self.c_symbol).reverse_dependencies.tri };
            ensure!(
                self.visible() > rev_dep_tri,
                "TODO: symbol visibility to low, cannot be assigned, probably deps not satisfied"
            );
            ensure!(
                value <= self.visible(),
                "TODO: symbol cannot be assigned above visibility"
            );
            ensure!(
                value >= rev_dep_tri,
                "TODO: symbol cannot be assigned below required value (inferred by reverse dependencies)"
            );
            ensure!(
                !(value == Tristate::Mod
                    && self.bridge.symbol("MODULES").unwrap().get_tristate_value() == Tristate::No),
                "TODO: symbol cannot be set to Mod because MODULES is not set"
            );
            Ok((self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value))
        };

        macro_rules! check_int_range {
            ($value: expr, $format: literal) => {
                let min = (self.bridge.vtable.c_sym_int_get_min)(self.c_symbol);
                let max = (self.bridge.vtable.c_sym_int_get_max)(self.c_symbol);
                ensure!(
                    $value >= min,
                    concat!(
                        "TODO: cannot set {}, desired value {",
                        $format,
                        "} must be >= {",
                        $format,
                        "}"
                    ),
                    self.name().unwrap(),
                    $value,
                    min
                );
                ensure!(
                    $value <= max,
                    concat!(
                        "TODO: cannot set {}, desired value {",
                        $format,
                        "} must be <= {",
                        $format,
                        "}"
                    ),
                    self.name().unwrap(),
                    $value,
                    max
                );
            };
        }

        let ret = match (self.symbol_type(), value) {
            (SymbolType::Boolean | SymbolType::Tristate, SymbolValue::Boolean(value)) => set_tristate(value.into())?,
            (SymbolType::Boolean, SymbolValue::Tristate(value)) if value != Tristate::Mod => set_tristate(value)?,
            (SymbolType::Tristate, SymbolValue::Tristate(value)) => set_tristate(value)?,
            (SymbolType::Int, SymbolValue::Int(value)) => {
                check_int_range!(value, "");
                let cstr = CString::new(value.to_string())?;
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::Hex, SymbolValue::Hex(value)) => {
                check_int_range!(value, ":#x");
                let cstr = CString::new(format!("{:#x}", value))?;
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::String, SymbolValue::String(value)) => {
                let cstr = CString::new(value)?;
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::Int, SymbolValue::Number(value)) => return self.set_symbol_value(SymbolValue::Int(value)),
            (SymbolType::Hex, SymbolValue::Number(value)) => return self.set_symbol_value(SymbolValue::Hex(value)),
            (st, v) => bail!(format!(
                "TODO: Cannot assign {v:?} to symbol {} ({st:?})",
                self.name().unwrap()
            )),
        };

        ensure!(ret, format!("Could not set symbol {:?}", self.name()));

        // TODO only recalculate the current symbol except when this was a choice?
        // not sure, check C code. Probably we need to go through all deps and recalculate those
        //self.recalculate();
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

    pub fn visible(&self) -> Tristate {
        unsafe { &*self.c_symbol }.visible
    }

    pub fn get_tristate_value(&self) -> Tristate {
        unsafe { &*self.c_symbol }.current_value.tri
    }

    pub fn get_string_value(&self) -> String {
        return unsafe { CStr::from_ptr((self.bridge.vtable.c_sym_get_string_value)(self.c_symbol)) }
            .to_str()
            .unwrap()
            .to_owned();
    }
}
