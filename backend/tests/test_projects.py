from app.services.github import repo_name_from_url, validate_github_url
import pytest


def test_valid_github_url():
    assert validate_github_url("https://github.com/owner/repo") == "https://github.com/owner/repo"
    assert validate_github_url("https://github.com/owner/repo.git") == "https://github.com/owner/repo"
    assert validate_github_url("https://github.com/owner/repo/") == "https://github.com/owner/repo"


def test_invalid_github_url():
    with pytest.raises(ValueError):
        validate_github_url("https://gitlab.com/owner/repo")
    with pytest.raises(ValueError):
        validate_github_url("not-a-url")


def test_repo_name():
    assert repo_name_from_url("https://github.com/acme/widget") == "widget"
