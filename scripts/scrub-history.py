"""Take four strings out of the history that this session put into it.

Two files gained them: the test that proved the examples carry nobody's real
work listed the private words in order to assert their absence, and the sync
documentation used the address of the machine this was built on as its example.
Both are fixed in the tree; this takes them out of the commits behind it.

Only blobs that are plainly those two files are touched, because the same two
letters turn up by chance inside fonts and PNGs.
"""

TEST_MARK = b"test_the_examples_carry_none_of_anyones_real_work"
PRIVATE = [
    (b'("Kamsiob", "Wellbeing", "Marchmont", "C9", "Riverbank Care", "@")',
     b'("Kamsiob", "Wellbeing", "Marchmont", "C9", "Riverbank Care", "@")'),
]
ADDRESS = (b"100.101.102.103", b"100.101.102.103")


def blob_callback(blob, metadata):
    data = blob.data
    if TEST_MARK in data:
        for old, new in PRIVATE:
            data = data.replace(old, new)
    # Text only: the address digits turn up by chance inside binaries.
    if ADDRESS[0] in data and b"\x00" not in data[:8192]:
        data = data.replace(*ADDRESS)
    blob.data = data
