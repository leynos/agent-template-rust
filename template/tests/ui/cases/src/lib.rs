//! Private-link UI fixture.

#[cfg(feature = "private-intra-doc-links")]
struct PrivateItem;

#[cfg(feature = "private-intra-doc-links")]
/// Return a [`PrivateItem`].
pub fn documented() {
    let _item = PrivateItem;
}
