"""CA-9 (ticket #32): the community files exist where GitHub reads them, the issue templates are YAML forms with
required fields and fixed dropdown values, and the README links to the guides."""

import re

import yaml

from ..conftest import ROOT

GITHUB = ROOT / ".github"
TEMPLATES = GITHUB / "ISSUE_TEMPLATE"
FORMS = sorted(p for p in TEMPLATES.glob("*.yml") if p.name != "config.yml")
# A form field of these types takes an answer; "markdown" only displays text.
ANSWERED = {"input", "textarea", "dropdown", "checkboxes"}


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_form_set_is_the_expected_one_and_no_markdown_template_is_left():
    assert [p.name for p in FORMS] == ["bug_report.yml", "feature_request.yml", "work_item.yml"]
    assert sorted(p.name for p in TEMPLATES.iterdir()) == [
        "bug_report.yml",
        "config.yml",
        "feature_request.yml",
        "work_item.yml",
    ], "a markdown issue template would shadow or duplicate a form"


def test_every_form_is_a_valid_issue_form_with_required_fields():
    for path in FORMS:
        form = load(path)
        assert {"name", "description", "body"} <= set(form), path.name
        assert isinstance(form["labels"], list) and "product:cloudassessor" in form["labels"], path.name
        ids = [item["id"] for item in form["body"] if item["type"] in ANSWERED]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate field ids"
        labels = [item["attributes"]["label"] for item in form["body"] if item["type"] in ANSWERED]
        assert len(labels) == len(set(labels)), f"{path.name}: duplicate field labels"
        required = [
            item
            for item in form["body"]
            if item["type"] in ANSWERED and (item.get("validations") or {}).get("required")
        ]
        assert required, f"{path.name}: no required field"
        for item in form["body"]:
            assert item["type"] in ANSWERED | {"markdown"}, f"{path.name}: {item['type']}"
            if item["type"] == "checkboxes":
                assert any(option.get("required") for option in item["attributes"]["options"]), path.name


def test_dropdowns_have_fixed_unique_values_and_are_required():
    seen = 0
    for path in FORMS:
        for item in load(path)["body"]:
            if item["type"] != "dropdown":
                continue
            seen += 1
            options = item["attributes"]["options"]
            assert len(options) >= 2 and len(options) == len(set(options)), f"{path.name}:{item['id']}"
            assert all(isinstance(option, str) and option.strip() for option in options)
            assert (item.get("validations") or {}).get("required") is True, f"{path.name}:{item['id']} not required"
    assert seen >= 6


def test_the_work_item_dropdowns_use_the_repository_label_values():
    form = load(TEMPLATES / "work_item.yml")
    options = {item["id"]: item["attributes"]["options"] for item in form["body"] if item["type"] == "dropdown"}
    assert options["priority"] == ["P1", "P2", "P3"]
    assert options["severity"] == ["high", "medium", "low"]
    assert options["workstream"] == ["ci", "dependencies", "docs", "governance", "release", "security", "testing"]


def test_blank_issues_are_off_and_the_contact_links_stay_inside_this_repository_or_the_lab_edition():
    config = load(TEMPLATES / "config.yml")
    assert config["blank_issues_enabled"] is False
    urls = [link["url"] for link in config["contact_links"]]
    assert urls and all(url.startswith("https://github.com/saulpatinojr/HCW-CloudAssessor_") for url in urls)
    assert any(url.endswith("/security/advisories/new") for url in urls), "the private route must be offered"


OWNER_EMAIL = "security@hybridcloudworks.com"
OWNER_SLA = "Expect an acknowledgement within 3 business days."


def test_contributing_and_code_of_conduct_exist_and_route_private_reports_through_github():
    for name in ("CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"):
        text = (GITHUB / name).read_text(encoding="utf-8")
        assert text.strip(), name
        # The owner's own contact and response time (written on main in SECURITY.md) are the only ones allowed; any
        # other e-mail address or time promise is invented.
        if name == "SECURITY.md":
            assert OWNER_EMAIL in text and OWNER_SLA in text, "the owner contact or acknowledgement time was removed"
            text = text.replace(OWNER_EMAIL, "").replace(OWNER_SLA, "")
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text), f"{name}: an e-mail address that is not the owner's"
        assert not re.search(r"business day|within \d|\d+ (hours|days)", text.lower()), f"{name}: an invented SLA"
    for name in ("CODE_OF_CONDUCT.md", "SECURITY.md"):
        assert "security/advisories/new" in (GITHUB / name).read_text(encoding="utf-8"), name
    assert ".github/CODE_OF_CONDUCT.md" in (GITHUB / "CONTRIBUTING.md").read_text(encoding="utf-8")


def test_the_readme_links_the_community_files_and_the_forms():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in (
        "(.github/CONTRIBUTING.md)",
        "(.github/CODE_OF_CONDUCT.md)",
        "(.github/SECURITY.md)",
        "(.github/ISSUE_TEMPLATE)",
    ):
        assert target in readme, target
