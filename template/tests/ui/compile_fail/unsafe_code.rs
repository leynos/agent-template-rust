#![forbid(unsafe_code)]

fn main() {
    let pointer = std::ptr::null::<u8>();
    unsafe {
        let _value = *pointer;
    }
}
