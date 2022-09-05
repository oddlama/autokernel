type CustomColor = (u8, u8, u8);

pub const COLOR_WHITE: CustomColor = (255, 255, 255);
pub const COLOR_MAIN: CustomColor = (220, 220, 220);
pub const COLOR_VERBOSE: CustomColor = (130, 130, 130);

#[macro_export]
macro_rules! colorize {
    ($string: expr, $color: ident) => {
        $string.truecolor($color.0, $color.1, $color.2)
    };
}

#[macro_export]
macro_rules! termcolor {
    ($color: ident) => {{
        use const_format::__cf_osRcTFl4A;
        use const_format::__write_pvariant;
        use const_format::concatcp;

        concatcp!("\x1b[38;2;", $color.0, ";", $color.1, ";", $color.2, "m")
    }};
}
