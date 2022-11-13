use anyhow::Result;
use autokernel::{
    bridge::{Bridge, SymbolValue, Tristate},
    script::{KConfig, LuaScript, Script},
};

mod setup_teardown;
use serial_test::serial;
use setup_teardown::{setup, teardown, teardown_full};

#[test]
#[serial(K)]
fn integration_setup() {
    teardown_full();
    setup();
}

#[test]
#[serial(K)]
fn integration_test_symbols() {
    let bridge = setup();

    println!("Testing tristate");
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
    sym.set_value_tracked(SymbolValue::Tristate(Tristate::Yes), file!().to_string(), line!(), None)
        .unwrap();
    assert_eq!(sym.get_tristate_value(), Tristate::Yes);
}

#[test]
#[serial(K)]
fn integration_test_kconfig() {
    let bridge = setup();
    println!("testing kconfig");
    let config = KConfig::from_content("good.kconfig".into(), include_str!("good.kconfig").into()).unwrap();
    test_script(&bridge, &config).unwrap();
    teardown();
}

#[test]
#[serial(K)]
fn integration_test_luaconfig() {
    let bridge = setup();
    println!("testing LuaScript");
    macro_rules! lua_test {
        ($name:literal, $code:expr) => {
            test_script(&bridge, &LuaScript::from_raw($name.into(), $code.into())).unwrap()
        };
    }

    macro_rules! lua_bad_test {
        ($name:literal, $code:expr) => {
            assert!(
                test_script(&bridge, &LuaScript::from_raw($name.into(), $code.into())).is_err(),
                $name
            )
        };
    }

    bridge
        .symbol("MODULES")
        .expect("this should have worked for test")
        .set_value_tracked(SymbolValue::Tristate(Tristate::Yes), file!().to_string(), line!(), None)
        .expect("this was for setting up the test");
    lua_test!(
        "assign syntax",
        r#"
        CONFIG_CRYPTO "y"
        CONFIG_CRYPTO "m"
        CONFIG_CRYPTO "n"
        CONFIG_CRYPTO(y)
        CONFIG_CRYPTO(m)
        CONFIG_CRYPTO(n)
    "#
    );
    lua_test!("test_full_config", include_str!("good.lua"));

    lua_bad_test!("bad_literal", "CONFIG_CRYPTO y");
    teardown();
}

fn test_script(bridge: &Bridge, script: &impl Script) -> Result<()> {
    script.apply(bridge)
}
