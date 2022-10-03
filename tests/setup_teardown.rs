use autokernel::bridge::Bridge;

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use log::info;
use log::error;
use anyhow::Context;

const TMP_TEST_DIR: &str = "autokernel-test";
const TEST_KERNEL: &str = "linux-5.19.1";

fn cache_kernel(kdir: &PathBuf) -> String{
    // latest="$(curl -s https://www.kernel.org/ | grep -A1 'stable:' | grep -oP '(?<=strong>).*(?=</strong.*)' | head -1)"
    let kernel_tar = format!("{}.tar.xz", &TEST_KERNEL);
    // test if kernel exists
    if kdir.join(&kernel_tar).exists() {
        info!("kernel tar already in cache");
        return kernel_tar;
    }
    panic!("{:?}", kdir.join(&kernel_tar));

    println!("downloading kernel {} ...", TEST_KERNEL);
    Command::new("wget")
        .arg("-q")
        .arg(format!("https://cdn.kernel.org/pub/linux/kernel/v5.x/{}", kernel_tar))
        .current_dir(&kdir)
        .status()
        .unwrap();
    return kernel_tar;
}

fn init_logger() {
    let _ = env_logger::builder().is_test(true).try_init();
}

fn setup_kernel(kdir: &PathBuf) -> PathBuf {
    let kernel_tar = cache_kernel(kdir);

    // remove kernel tar and folder if they already exists
    info!("cleaning previous test if exists");
    if kdir.join(TEST_KERNEL).exists() {
        Command::new("rm")
            .arg("-r")
            .arg(&TEST_KERNEL)
            .current_dir(&kdir)
            .status()
            .unwrap();
    }


    info!("extracting kernel {} ...", TEST_KERNEL);
    Command::new("tar")
        .arg("-xvf")
        .arg(&kernel_tar)
        .current_dir(&kdir)
        .stdout(Stdio::null())
        .status()
        .unwrap();
    kdir.join(TEST_KERNEL)
}

pub fn setup() -> Bridge {
    init_logger();
    error!("{:?}", env::temp_dir());
    let kdir = env::temp_dir().join(&TMP_TEST_DIR);
    info!("creating {} directory", &kdir.display());
    println!("creating {} directory", &kdir.display());
    fs::create_dir_all(&kdir).unwrap();
    let kdir = kdir.canonicalize().context(format!("tmp {:?}, folder {:?}", env::temp_dir(), TMP_TEST_DIR)).unwrap();
    let kdir = setup_kernel(&kdir);
    Bridge::new(kdir).unwrap()
}

pub fn teardown() {
    let kdir = env::temp_dir().join(&TMP_TEST_DIR).join(TEST_KERNEL);
    // remove kernel tar and folder if they already exists
    println!("cleaning up (leaving tar)");
    Command::new("rm").arg("-r").arg(&kdir).status().expect("cleanup failed");
}