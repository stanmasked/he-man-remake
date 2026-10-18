//! Copy into an upstream NeXium checkout: nexium-loader/tests/heman_real_nro.rs
//! This test uses ONLY asset-free homebrew binaries built in the same CI run.
use nexium_loader::Loader;
use std::{env, fs, path::Path};

fn check_nro(path: &Path, expect_fixed: bool) {
    let data = fs::read(path).expect("read generated homebrew .nro");
    assert_eq!(&data[16..20], b"NRO0", "genuine devkitPro wrapper");
    let actual = Loader::load_nro(path.to_str().expect("utf8 path"));
    if !expect_fixed {
        let error = match actual {
            Ok(_) => panic!("unpatched NeXium unexpectedly accepted the original NRO"),
            Err(error) => error,
        };
        assert!(error.contains("Data segment out of bounds"), "unexpected error: {error}");
        println!("Unpatched NeXium reproduces loader failure: {error}");
        return;
    }
    let nro = actual.expect("patched NeXium must load normal devkitPro NRO");
    let declared_size = nro.header.size as usize;
    assert!(declared_size <= data.len());
    assert_eq!(nro.text.offset, 0, "original text begins at image byte zero");
    assert_eq!(&nro.nro_bytes()[..16], &data[..16]);
    for (seg, bytes) in [
        (&nro.text, nro.text_data()),
        (&nro.ro, nro.ro_data()),
        (&nro.data, nro.data_data()),
    ] {
        let start = seg.offset as usize;
        let end = start + seg.size as usize;
        assert!(end <= declared_size);
        assert_eq!(seg.mmap_range, start..end);
        assert_eq!(bytes, &data[start..end], "byte-exact code segment mapping");
    }
    assert_eq!(&nro.text_data()[..4], &data[..4]);
    println!(
        "Patched NeXium loaded {}: {} bytes, data=[{:#x}..{:#x}]",
        path.display(),
        declared_size,
        nro.data.offset,
        nro.data.offset as usize + nro.data.size as usize
    );
}

#[test]
fn exercise_exact_real_asset_free_homebrew_nros() {
    let expect_fixed = env::var("HEMAN_EXPECT_FIXED").as_deref() == Ok("1");
    for name in ["heman_minimal_guest_probe.nro", "heman_raster_probe.nro"] {
        let directory = env::var("HEMAN_TEST_NROS")
            .expect("set HEMAN_TEST_NROS to CI artifact directory");
        check_nro(&Path::new(&directory).join(name), expect_fixed);
    }
}
