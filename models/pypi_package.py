from models import package
from models.package import Package
from jobs import update_registry
from jobs import Update

from app import db
from sqlalchemy.dialects.postgresql import JSONB
from time import time
from validate_email import validate_email
from distutils.version import StrictVersion
import requests
import hashlib

from models.person import get_or_make_person
from models.github_repo import GithubRepo
from models.zip_getter import ZipGetter
from util import elapsed
from python import parse_requirements_txt



class PypiPackage(Package):
    class_host = "pypi"

    __mapper_args__ = {
        'polymorphic_identity': 'pypi'
    }

    def __repr__(self):
        return u'<PypiPackage {name}>'.format(
            name=self.id)

    @property
    def language(self):
        return "python"


    @property
    def source_url(self):
        if not self.api_raw:
            return None

        if "releases" in self.api_raw and self.api_raw["releases"]:
            versions = self.api_raw["releases"].keys()

            try:
                versions.sort(key=StrictVersion, reverse=True)
            except ValueError:
                versions #give up sorting, just go for it

            for version in versions:
                release_dict = self.api_raw["releases"][version]
                for url_dict in release_dict:
                    if "packagetype" in url_dict:

                        # trying these in priority order
                        valid_type = ["bdist_wheel", "bdist_egg", "sdist", "bdist_dumb"]
                        for packagetype in valid_type:
                            if url_dict["packagetype"]==packagetype:
                                if "url" in url_dict and url_dict["url"].startswith("http"):
                                    return url_dict["url"]

            if "download_url" in self.api_raw["info"] and self.api_raw["info"]["download_url"]:
                if self.api_raw["info"]["download_url"].startswith("http"):
                    return self.api_raw["info"]["download_url"]

        return None


    def save_host_contributors(self):
        author = self.api_raw["info"]["author"]
        author_email = self.api_raw["info"]["author_email"]

        if not author:
            return False

        if author_email and validate_email(author_email):
            person = get_or_make_person(name=author, email=author_email)
        else:
            person = get_or_make_person(name=author)

        self._save_contribution(person, "author")


    def set_github_repo_ids(self):
        q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
        q = q.filter(GithubRepo.bucket.contains({"setup_py_name": self.project_name}))
        q = q.order_by(GithubRepo.api_raw['stargazers_count'].cast(db.Integer).desc())

        start = time()
        row = q.first()
        print "Github repo query took {}".format(elapsed(start, 4))

        if row is None:
            return None

        else:
            print "Setting a new github repo for {}: {}/{}".format(
                self,
                row[0],
                row[1]
            )
            self.github_owner = row[0]
            self.github_repo_name = row[1]
            self.bucket["matched_from_github_metadata"] = True


    def _get_files(self, filenames_to_get):

        print "getting requires files for {} from {}".format(
            self.id, self.source_url)
        if not self.source_url:
            print "No source_url, so skipping"
            return {"error": "error_no_source_url"}

        getter = ZipGetter(self.source_url)

        ret = getter.download_and_extract_files(filenames_to_get)

        if getter.error:
            print "Problems with the downloaded zip, quitting without getting filenames."
            ret = {"error": "error_with_zip"}

        return ret


    def set_requires_files(self):
        # from https://pythonhosted.org/setuptools/formats.html#dependency-metadata
        filenames_to_get = [
            "/requires.txt",
            "/metadata.json",
            "/METADATA"
        ]
        self.requires_files = self._get_files(filenames_to_get)
        return self.requires_files

    def set_setup_py(self):
        res = self._get_files(["setup.py"])
        if "error" in res:
            self.setup_py = res["error"]  # save the error string

        else:
            try:
                self.setup_py = res["setup.py"]

                # major hack! comment this in ONLY when there's nothing
                # left to check but weird files that break on UTF-8 errors.
                #self.setup_py = "error_utf8"

                self.setup_py_hash = hashlib.md5(res["setup.py"]).hexdigest()

            except KeyError:
                # seems there is in setup.py here.
                self.setup_py = "error_not_found"

        return self.setup_py



    def set_api_raw(self):
        requests.packages.urllib3.disable_warnings()
        url = 'https://pypi.python.org/pypi/{}/json'.format(self.project_name)
        r = requests.get(url)
        try:
            self.api_raw = r.json()
        except ValueError:
            self.api_raw = {"error": "no_json"}


    def set_host_deps(self):
        core_requirement_lines = ""

        if "METADATA" in self.requires_files:
            requirement_text = self.requires_files["METADATA"]
            # exclude everything after a heading
            core_requirement_list = []
            for line in requirement_text.split("\n"):

                # see spec at https://www.python.org/dev/peps/pep-0345/#download-url
                # "Requires" start is depricated
                if line.startswith("Requires-Dist:") or line.startswith("Requires:"):
                    line = line.replace("Requires-Dist:", "")
                    line = line.replace("Requires:", "")
                    if ";" in line:
                        # has extras in it... so isn't in core requirements, so skip
                        pass
                    else:
                        core_requirement_list += [line]
            core_requirement_lines = "\n".join(core_requirement_list)

        elif "requires.txt" in self.requires_files:
            requirement_text = self.requires_files["requires.txt"]

            # exclude everything after a heading
            core_requirement_list = []
            for line in requirement_text.split("\n"):
                if line.startswith("["):
                    break
                core_requirement_list += [line]
            core_requirement_lines = "\n".join(core_requirement_list)

        deps = parse_requirements_txt(core_requirement_lines)

        print "found requirements={}\n\n".format(deps)
        if not deps:
            self.host_deps = []
            return None

        # see if is in pypi, case insensitively, getting normalized case
        deps_in_pypi = []
        for dep in deps:
            if dep.lower() in pypi_package_names:
                pypi_package_normalized_case = pypi_package_names[dep.lower()]
                deps_in_pypi.append(pypi_package_normalized_case)

        if len(deps_in_pypi) != len(deps):
            print "some deps not in pypi for {}:{}".format(
                self.id, set(deps) - set(deps_in_pypi))
            print deps
            print deps_in_pypi
        self.host_deps = deps_in_pypi


    def set_tags(self):
        self.tags = []
        tags_to_reject = [
            "Python Modules",
            "Libraries",
            "Software Development"
        ]
        try:
            pypi_classifiers = self.api_raw["info"]["classifiers"]
        except KeyError:
            print "no keywords for {}".format(self)
            return None

        working_tag_list = []
        for classifier in pypi_classifiers:
            if not classifier.startswith("Topic"):
                continue

            # the first 'tag' is useless
            my_tags = classifier.split(" :: ")[1:]
            working_tag_list += my_tags

        unique_tags = list(set(working_tag_list))
        for tag in unique_tags:
            if len(tag) > 1 and tag not in tags_to_reject:
                self.tags.append(tag)

        if len(self.tags):
            print "set tags for {}: {}".format(self, ",".join(self.tags))
        else:
            print "found no tags for {}".format(self)

        return self.tags



def get_pypi_package_names(force_lower=True):
    """
        returns a dict with the key as the lowercase name and the value as the orig cased name
    """
    start_time = time()
    pypi_q = db.session.query(PypiPackage.project_name)
    pypi_lib_names = [r[0] for r in pypi_q.all()]

    pypi_lib_lookup = dict([(name.lower(), name) for name in pypi_lib_names])

    print "got {} PyPi project names in {}sec.".format(
        len(pypi_lib_lookup),
        elapsed(start_time)
    )

    return pypi_lib_lookup










