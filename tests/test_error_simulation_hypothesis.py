import random
from hypothesis import given, strategies as st, assume
from genecoder.error_simulation import introduce_errors
from genecoder.channel_sim import simulate_errors, NUCLEOTIDES


def undo_simulate_errors(original: str, mutated: str, p: float, seed: int) -> str:
    rng = random.Random(seed)
    result = []
    for orig_nt, mut_nt in zip(original, mutated):
        if rng.random() < p:
            rng.choice([n for n in NUCLEOTIDES if n != orig_nt])
            result.append(orig_nt)
        else:
            result.append(mut_nt)
    return "".join(result)


@given(
    seq=st.text(alphabet=st.sampled_from(NUCLEOTIDES), min_size=0, max_size=50),
    p=st.floats(min_value=0.0, max_value=1.0),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_simulate_errors_roundtrip(seq: str, p: float, seed: int) -> None:
    mutated = simulate_errors(seq, p_error=p, rng=random.Random(seed))
    recovered = undo_simulate_errors(seq, mutated, p, seed)
    assert recovered == seq
    assert len(mutated) == len(seq)


@given(
    seq=st.text(alphabet=st.sampled_from(NUCLEOTIDES), min_size=0, max_size=50),
    sub=st.floats(min_value=0.0, max_value=1.0),
    ins=st.floats(min_value=0.0, max_value=1.0),
    dele=st.floats(min_value=0.0, max_value=1.0),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_introduce_errors_length_bounds(
    seq: str, sub: float, ins: float, dele: float, seed: int
) -> None:
    assume(sub + ins + dele <= 1.0)
    mutated = introduce_errors(
        seq,
        substitution_prob=sub,
        insertion_prob=ins,
        deletion_prob=dele,
        rng=random.Random(seed),
    )
    assert 0 <= len(mutated) <= 2 * len(seq)

