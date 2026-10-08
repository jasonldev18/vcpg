import pytest

from topk import main


def test_prints_the_top_two(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--k", "2"])
    assert capsys.readouterr().out.split() == ["alpha", "gamma"]


@pytest.mark.parametrize("k", ["0", "-3", "two"])
def test_rejects_bad_k(k: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--k", k])
    assert "k" in capsys.readouterr().err
