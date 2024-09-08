use autokernel::bridge::Bridge;

use anyhow::Context;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};

const TMP_TEST_DIR: &str = "autokernel-test";
const TEST_KERNEL: &str = "linux-5.19.1";

fn cache_kernel(kdir: &PathBuf) -> String {
    // latest="$(curl -s https://www.kernel.org/ | grep -A1 'stable:' | grep -oP '(?<=strong>).*(?=</strong.*)' | head -1)"
    let kernel_tar = format!("{}.tar.xz", &TEST_KERNEL);
    // test if kernel exists
    if kdir.join(&kernel_tar).exists() {
        println!("kernel tar already in cache");
        return kernel_tar;
    }

    println!("downloading kernel {} ...", TEST_KERNEL);
    Command::new("wget")
        .arg("-q")
        .arg(format!("https://cdn.kernel.org/pub/linux/kernel/v5.x/{}", kernel_tar))
        .current_dir(kdir)
        .status()
        .unwrap();
    kernel_tar
}

fn setup_kernel(kdir: &PathBuf) -> PathBuf {
    let kernel_tar = cache_kernel(kdir);

    let res = kdir.join(TEST_KERNEL);
    if res.exists() {
        return res;
    }

    // remove kernel tar and folder if they already exists
    //println!("cleaning previous test if exists");
    //if kdir.join(TEST_KERNEL).exists() {
    //    Command::new("rm")
    //        .arg("-r")
    //        .arg(&TEST_KERNEL)
    //        .current_dir(&kdir)
    //        .status()
    //        .unwrap();
    //}

    println!("extracting kernel {} ...", TEST_KERNEL);
    Command::new("tar")
        .arg("-xvf")
        .arg(&kernel_tar)
        .current_dir(kdir)
        .stdout(Stdio::null())
        .status()
        .unwrap();
    res
}

pub fn setup() -> Bridge {
    let kdir = env::temp_dir().join(TMP_TEST_DIR);
    println!("creating {} directory", &kdir.display());
    fs::create_dir_all(&kdir).unwrap();
    let kdir = kdir
        .canonicalize()
        .context(format!("tmp {:?}, folder {:?}", env::temp_dir(), TMP_TEST_DIR))
        .unwrap();
    let kdir = setup_kernel(&kdir);
    Bridge::new(kdir, None).unwrap()
}

pub fn teardown() {
    // Nothing to do for now
}

pub fn teardown_full() {
    if let Err(_e) = fs::remove_dir_all(env::temp_dir().join(TMP_TEST_DIR).join(TEST_KERNEL)) {
        eprintln!("could not remove tmp dir");
    }
}
