import pytest
from genecoder.formats import from_fasta


def test_from_fasta_lowercase_error_line_number():
    content = ">seqX\nACGT\natgc\n"
    with pytest.raises(ValueError, match="line 3"):
        from_fasta(content)
