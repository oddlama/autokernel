use anyhow::Result;
use autokernel::{
    bridge::{Bridge, SymbolValue, Tristate},
    config::{Config, KConfig, LuaConfig},
};
use log::info;

mod setup_teardown;
use serial_test::serial;
use setup_teardown::{setup, teardown, teardown_full};

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
    assert_eq!(sym.get_tristate_value(), Tristate::No);

    // Setting
    sym.set_value_tracked(SymbolValue::Tristate(Tristate::Yes)).unwrap();
    assert_eq!(sym.get_tristate_value(), Tristate::Yes);
}

#[test]
#[serial(K)]
fn integration_test_kconfig() {
    let bridge = setup();
    info!("testing kconfig");
    let config = KConfig::from_lines(include_str!("good.kconfig").lines()).unwrap();
    test_config(&bridge, &config);
    teardown();
}

#[test]
#[serial(K)]
fn integration_test_luaconfig() {
    let bridge = setup();
    info!("testing LuaConfig");
    macro_rules! lua_test {
        ($name:literal, $code:expr) => {
            test_config(&bridge, &LuaConfig::from_raw($name.into(), $code.into())).unwrap()
        };
    }

    macro_rules! lua_bad_test {
        ($name:literal, $code:expr) => {
            assert!(
                test_config(&bridge, &LuaConfig::from_raw($name.into(), $code.into())).is_err(),
                $name
            )
        };
    }

    bridge
        .symbol("MODULES")
        .expect("this should have worked for test")
        .set_value_tracked(SymbolValue::Tristate(Tristate::Yes))
        .expect("this was for setting up the test");
    lua_test!(
        "assign syntax",
        r#"
        CONFIG_CRYPTO "y"
        CONFIG_CRYPTO "m"
        CONFIG_CRYPTO "n"
        CONFIG_CRYPTO(yes)
        CONFIG_CRYPTO(mod)
        CONFIG_CRYPTO(no)
        CONFIG_CRYPTO(y)
        CONFIG_CRYPTO(m)
        CONFIG_CRYPTO(n)
    "#
    );
    lua_test!("test_full_config", include_str!("good.lua"));

    lua_bad_test!("bad_literal", "CONFIG_CRYPTO y");
    teardown();
}

fn test_config(bridge: &Bridge, config: &impl Config) -> Result<()> {
    config.apply_kernel_config(&bridge)?;
    Ok(())
}
