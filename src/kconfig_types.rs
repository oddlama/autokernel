#![allow(dead_code)]
use serde::Deserialize;

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Expr {
    pub dummy: Option<String>,
    pub left: Direction,
    pub right: Direction,
    #[serde(rename = "type")]
    pub typ: String,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Menu {
    pub dep: Option<Expr>,
    pub flags: String,
    pub help: Option<String>,
    pub visibility: Option<String>,
}
#[derive(Deserialize, Debug)]
#[serde(untagged)]
pub enum Direction {
    None,
    Ptr(String),
    There(Box<Expr>),
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Property {
    #[serde(rename = "type")]
    pub typ: String,
    pub text: Option<String>,
    pub visible: Dep,
    pub expr: Option<Expr>, //Option<Expr>,
    pub menu: Menu,         //Option<Menu>,
    pub file: Option<String>,
    pub lineno: String,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Dep {
    pub expr: Option<Expr>,
    pub tri: String,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Symbol {
    pub curr: Curr,
    pub def: Def,
    pub dir_dep: Dep,
    pub flags: String,
    pub implied: Dep,
    pub name: Option<String>,
    pub properties: Vec<Property>,
    pub ptr: String,
    pub rev_dep: Dep,
    #[serde(rename = "type")]
    pub typ: String,
    pub visible: String,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Symbols {
    pub symbols: Vec<Symbol>,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Curr {
    pub tri: String,
    pub val: Option<String>,
}

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Def {
    pub user: Curr,
    pub auto: Curr,
    pub def3: Curr,
    pub def4: Curr,
}
#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct TriStr {
    pub tri: String,
}
