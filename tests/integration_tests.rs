use autokernel::{bridge::{SymbolValue, Tristate, Bridge}, config::{Config, LuaConfig, KConfig}};
use rlua::Lua;
use log::info;

mod setup_teardown;
use setup_teardown::{setup, teardown, teardown_full};
use serial_test::serial;

#[test]
#[serial(K)]
fn integration_setup() {
    teardown_full();
    setup();
}

// TODO use test_env_logger
// TODO only download kernel once, then run many tests on it
#[test]
#[serial(K)]
fn integration_test_symbols() {
    let bridge = setup();

    info!("Testing tristate");
    test_symbol_tristate(&bridge);
    //TODO more tests

    teardown();
}

fn test_symbol_tristate(bridge: &Bridge) {
    const SYMBOL: &str = "CMDLINE_BOOL";
    let mut sym = bridge.symbol(SYMBOL).unwrap();

    // Getting
    assert_eq!(sym.name().unwrap(), SYMBOL);
    assert_eq!(*sym.get_value(), Tristate::No);

    // Setting
    sym.set_symbol_value(SymbolValue::Tristate(Tristate::Yes)).unwrap();
    assert_eq!(*sym.get_value(), Tristate::Yes);
}

#[test]
#[serial(K)]
fn integration_test_kconfig() {
    let bridge = setup();
    info!("testing kconfig");
    let config = KConfig::from_lines(include_str!("good.kconfig").lines()).unwrap();
    test_config(&config);
    teardown();
}


#[test]
#[serial(K)]
fn integration_test_luaconfig() {
    let bridge = setup();
    info!("testing LuaConfig");
    let config = LuaConfig::from_raw(
        "good.lua".into(),
        include_str!("good.lua").into(),
    );
    teardown();
}

fn test_config(config: &impl Config) {
    //todo

}
