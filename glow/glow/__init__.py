# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import ConfigParser
import errno
import json
import os
import sys

import colorama
import requests
import sarge

from glow import helpers, messages


class Glow(object):

    workspace = None
    version_file = None
    version = None
    branches = None

    glow_file = None
    glow_config = None

    @staticmethod
    def _change_branch(branch_name):
        output = sarge.run("git checkout {}".format(branch_name),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("Branch \"{}\" not found.".format(branch_name))
            return False

    @staticmethod
    def _pull_branch(branch_name, create_branch=False):
        if create_branch:
            output = sarge.run("git pull origin {} &&"
                               "git checkout -b {}".format(branch_name, branch_name),
                               stdout=sarge.Capture(),
                               stderr=sarge.Capture())
        else:
            output = sarge.run("git checkout {} &&"
                               "git pull origin {}".format(branch_name, branch_name),
                               stdout=sarge.Capture(),
                               stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("An error occurred while pulling branch \"{}\".".format(branch_name))

        else:
            messages.success("Branch \"{}\" pulled.".format(branch_name))

        return not bool(output.returncode)

    @staticmethod
    def _push_branch(branch_name):
        output = sarge.run("git checkout {} &&"
                           "git push origin {}".format(branch_name, branch_name),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("An error occurred while pushing branch \"{}\".".format(branch_name))

        else:
            messages.success("Branch \"{}\" pushed".format(branch_name))

        return not bool(output.returncode)

    @staticmethod
    def _pull_repository():
        """Pull develop and master branches and tags from origin and prune remote branches"""
        output = sarge.run("git checkout develop && "
                           "git pull origin develop && "
                           "git checkout master && "
                           "git pull origin master && "
                           "git fetch --tags && "
                           "git remote prune origin",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("An error occurred while pulling the repository.")

        else:
            messages.success("Repository pulled.")

        return not bool(output.returncode)

    @staticmethod
    def _push_repository():
        """Push develop and master branches and tags to origin"""
        output = sarge.run("git checkout develop && "
                           "git push origin develop && "
                           "git checkout master && "
                           "git push origin master && "
                           "git push origin --tags",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("An error occurred while pushing the repository.")

        else:
            messages.success("Repository pushed.")

        return not bool(output.returncode)

    @staticmethod
    def _generate_changelog(branch_from, branch_to):
        """Generate changelog between two branches"""
        output = sarge.run("git log {}..{} --pretty=format:\"%s\" --date=short".format(branch_from, branch_to),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to generate changelog")
            return False
        else:
            return "".join(["- " + line + "\n" for line in output.stdout.text.split("\n")])

    def _str_version(self, version=None):
        """Cast version dict to string"""
        if not version:
            version = self.version
        return "{}.{}.{}".format(version["master"], version["release"], version["hotfix"])

    def _get_version(self):
        """Read application version from file"""
        if os.path.exists(self.version_file):
            version = open(self.version_file, "r").read()
            master, release, hotfix = version.split(".")
            self.version = {
                "master": int(master),
                "release": int(release),
                "hotfix": int(hotfix),
            }
            return self.version

        else:
            return False

    def _set_version(self, version=None):
        """Write application version to file"""
        if not version:
            version = self.version

        else:
            self.version = version

        try:
            open(self.version_file, "w").write(self._str_version(version))
            return True

        except Exception as error:
            messages.critical(error)
            return False

    def _get_glow_configuration(self):
        """Read application glow parameters from file"""
        if os.path.exists(self.glow_file):
            self.glow_config = ConfigParser.RawConfigParser()
            self.glow_config.read(self.glow_file)
            return self.glow_config

        else:
            return False

    def _get_branches(self):
        """Get available branches"""
        output = sarge.run("git branch -a",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to get branches.")
            return False

        self._branches = [name.replace("*", "").strip() for name in output.stdout.text.split("\n") if name != ""]
        return self._branches

    def _feature_exists(self, issue_id):
        issue_id = str(issue_id)
        feature_name = "feature/{}-{}_".format(self.glow_config.get("jira", "project_key"), issue_id)
        for branch in self._branches:
            if feature_name in branch:
                return True
        return False

    def _get_feature_branch(self, issue_id):
        issue_id = str(issue_id)
        for branch in self._branches:
            if issue_id in branch and "remotes" not in branch:
                return branch
        return None

    # def get_hotfix_branch(self, issue_id):
    #     issue_id = str(issue_id)
    #     for branch in self._branches:
    #         if issue_id in branch and "remotes" not in branch:
    #             return branch
    #     return None

    def __init__(self):
        """Initialize Github Flow CLI"""

        # Initialize Colorama
        colorama.init(autoreset=True)

        # Retrieve Workspace
        output = sarge.run("git rev-parse --show-toplevel",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 1:
            messages.critical("Not in a git repository")
            sys.exit(errno.ENOENT)

        else:
            self.workspace = helpers.remove_new_line(output.stdout.text)
            messages.info("Workspace: {}".format(self.workspace))

        # Retrieve application version
        messages.log("Retrieve application version...")
        self.version_file = os.path.join(self.workspace, "version")

        if not self._get_version():
            create_a_version_file = messages.question("Create a Version file? [y/n] ")

            if create_a_version_file.lower() != "y":
                messages.warning("Quitting...")
                sys.exit(errno.EPERM)

            version = {
                "master": 0,
                "release": 0,
                "hotfix": 0
            }
            self._set_version(version)

            messages.success("Version file created.")

        messages.info("Current application version: {}".format(self._str_version()))

        # Retrieve glow file
        messages.log("Retrieve glow configuration...")
        self.glow_file = os.path.join(self.workspace, ".glow")

        if not self._get_glow_configuration():
            create_a_glow_file = messages.question("Create a FlowHub file? [y/n] ")

            if create_a_glow_file.lower() != "y":
                messages.warning("Quitting...")
                sys.exit(errno.EPERM)

            self.glow_config = ConfigParser.RawConfigParser()

            self.glow_config.add_section("github")
            github_url = messages.question("Github URL? ")
            self.glow_config.set("github", "url", github_url)

            github_token = messages.question("Github Token? ")
            self.glow_config.set("github", "token", github_token)

            github_repository_name = messages.question("Github Repository Name? [:owner/:name] ")
            self.glow_config.set("github", "repository_name", github_repository_name)

            self.glow_config.add_section("jira")
            jira_project_key = messages.question("Jira Project Key? ")
            self.glow_config.set("jira", "project_key", jira_project_key)

            with open(self.glow_file, "wb") as file_resource:
                self.glow_config.write(file_resource)

            messages.success("FlowHub file created.")

        # Retrieve available branches
        messages.log("Retrieve available branches...")
        self._get_branches()

    """
        Feature methods
        - start
        - finish
        - cancel
    """

    def start_feature(self, issue_id, description):
        try:
            issue_id = int(issue_id)

        except ValueError:
            messages.critical("IssueID \"{}\" is not valid.".format(issue_id))
            sys.exit(1)

        except TypeError:
            messages.critical("IssueID is not set.")
            sys.exit(1)

        if not description or not len(description):
            messages.critical("description can\"t be empty.")
            sys.exit(1)

        feature_name = "{}-{}_{}".format(self.glow_config.get("jira", "project_key"), issue_id, description)

        if self._feature_exists(issue_id):
            messages.error("A feature locally exists for IssueID {}.".format(issue_id))
            return False

        create_feature = messages.question("Validate this feature name -> feature/{}? [y/n] ".format(feature_name))
        if create_feature.lower() != "y":
            messages.warning("Quitting...")
            sys.exit(1)

        # Create remote and local branch
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        response = session.get("{}/api/v3/repos/{}/git/refs/heads".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers)

        if response.status_code != 200:
            messages.critical("An error occurred while retrieving refs.")
            return False

        commit_ref = None
        for item in response.json():
            if item["ref"] == "refs/heads/develop":
                commit_ref = item["object"]["sha"]
                break

        if not commit_ref:
            messages.critical("develop branch was not found on remote repository.")
            return False

        payload = {
            "ref": "refs/heads/feature/{}".format(feature_name),
            "sha": commit_ref
        }

        response = session.post("{}/api/v3/repos/{}/git/refs".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New branch: feature/{} created".format(feature_name))

            if self._pull_branch("feature/{}".format(feature_name), create_branch=True):
                messages.success("Switched to a new branch \"feature/{}\".".format(feature_name))
                return True

            else:
                messages.critical("Unable to checkout to branch: feature/{}".format(feature_name))
                return False

        elif response.status_code == 422:
            messages.error("Feature branch feature/{} already exists.".format(feature_name))
            return False

        else:
            messages.critical("Feature branch feature/{} can not be created ({}: {}).".format(
                feature_name,
                response.status_code,
                response.json()["message"]))
            return False

    def review_feature(self, issue_id, description=None):
        try:
            issue_id = int(issue_id)

        except ValueError:
            messages.critical("IssueID \"{}\" is not valid.".format(issue_id))
            sys.exit(1)

        except TypeError:
            messages.critical("IssueID is not set.")
            sys.exit(1)

        if not self._feature_exists(issue_id):
            messages.error("There is no feature for IssueID {}.".format(issue_id))
            sys.exit(1)

        feature_name = self._get_feature_branch(issue_id)

        # Push feature branch to origin
        messages.log("Push feature branch to origin")
        self._push_branch(feature_name)

        # Pull last modifications from develop
        messages.log("Pull last modifications from develop")
        self._pull_branch("develop")

        # Create a Pull Request for this feature branch into develop
        messages.log("Create a Pull Request for this feature branch into develop")
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        title, body = feature_name.replace("feature/", "").split("_", 1)
        payload = {
            "title": title,
            "body": body.replace("-", " ").capitalize(),
            "head": feature_name,
            "base": "develop"
        }

        response = session.post("{}/api/v3/repos/{}/pulls".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New Pull Request created: {}".format(response.json()["html_url"]))
            return True

        else:
            messages.critical(response.json()["message"])
            for error in response.json()["errors"]:
                messages.error(error["message"])
            return False

    def cancel_feature(self, issue_id, description=None):
        try:
            issue_id = int(issue_id)

        except ValueError:
            messages.critical("IssueID \"{}\" is not valid.".format(issue_id))
            sys.exit(1)

        except TypeError:
            messages.critical("IssueID is not set.")
            sys.exit(1)

        if not self._feature_exists(issue_id):
            messages.error("There is no feature for IssueID {}.".format(issue_id))
            sys.exit(1)

        feature_name = self._get_feature_branch(issue_id)
        messages.log(feature_name)

    """
    Release methods
    """
    def start_release(self, is_master=False):
        """Open an application release"""
        self._pull_repository()

        # Change version
        if is_master:
            self.version["master"] += 1
        else:
            self.version["release"] += 1

        self.version["hotfix"] = 0

        create_release = messages.question("Validate this release name -> release/{}? [y/n] ".format(
            self._str_version()))
        if create_release.lower() != "y":
            messages.warning("Quitting...")
            sys.exit(errno.ENOMSG)

        # Create remote and local branch
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        response = session.get("{}/api/v3/repos/{}/git/refs/heads".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers)

        if response.status_code != 200:
            messages.critical("An error occurred while retrieving refs.")
            return False

        commit_ref = None
        for item in response.json():
            if item["ref"] == "refs/heads/develop":
                commit_ref = item["object"]["sha"]
                break

        if not commit_ref:
            messages.critical("develop branch was not found on remote repository.")
            return False

        payload = {
            "ref": "refs/heads/release/{}".format(self._str_version()),
            "sha": commit_ref
        }

        response = session.post("{}/api/v3/repos/{}/git/refs".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New branch: release/{} created".format(self._str_version()))

            if self._pull_branch("release/{}".format(self._str_version()), create_branch=True):
                messages.success("Switched to a new branch \"release/{}\".".format(self._str_version()))

                with sarge.Capture() as output:
                    self._set_version()
                    sarge.run("git add version &&"
                              "git commit -m \"Update version to {}\" &&"
                              "git push origin release/{}".format(self._str_version(), self._str_version()),
                              stdout=output,
                              stderr=output)
                return True

            else:
                messages.critical("Unable to checkout to branch: release/{}".format(self._str_version()))
                return False

        elif response.status_code == 422:
            messages.error("Feature branch release/{} already exists.".format(self._str_version()))
            return False

        else:
            messages.critical("Release branch release/{} can not be created ({}: {}).".format(
                self._str_version(),
                response.status_code,
                response.json()["message"]))
            return False

    def review_release(self, is_master=False):
        output = sarge.run("git checkout release/{}".format(self._str_version()),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("No release found")
            return False

        self._push_branch("release/{}".format(self._str_version()))

        # Create a Pull Request
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        branch_from = "master"
        branch_to = "release/{}".format(self._str_version())

        changelog = self._generate_changelog(branch_from, branch_to)

        if not changelog:
            return False

        payload = {
            "title": "Release {}".format(self._str_version()),
            "body": changelog,
            "head": branch_to,
            "base": branch_from,
        }

        response = session.post("{}/api/v3/repos/{}/pulls".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New Pull Request created: {}".format(response.json()["html_url"]))
            return True

        else:
            messages.critical(response.json()["message"])
            for error in response.json()["errors"]:
                messages.error(error["message"])
            return False

    def finish_release(self, is_master=False):
        self._pull_repository()

        output = sarge.run("git show master\^1",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to find previous commit on \"master\" branch.")
            return False

        commit_ref = output.stdout.text.split("\n")[0].replace("commit ", "")
        changelog = self._generate_changelog(commit_ref, "master")

        if not changelog:
            return False

        messages.info("Tag version {}.".format(self._str_version()))
        output = sarge.run("git tag -a {} -m \"{}\"".format(
            self._str_version(),
            changelog.replace("\"", "\\\"")),
            stdout=sarge.Capture(),
            stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to tag version {}.".format(self._str_version()))
            return False

        messages.info("Merge tag \"{}\" into \"develop\".".format(self._str_version()))
        merge_message = "Merge tag \"{}\" into \"develop\"\n\n{}".format(self._str_version(), changelog)
        output = sarge.run("git push origin --tags && "
                           "git checkout develop && "
                           "git merge --no-ff {} -m \"{}\" -X theirs".format(self._str_version(), merge_message),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to merge tag into \"develop\"")
            return False

        self._push_branch("develop")

        output = sarge.run("git branch -d release/{} &&"
                           "git push origin :release/{}".format(self._str_version(), self._str_version()),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.warning("Unable to remove release branches.")
            return False

        messages.success("Release {} finished.".format(self._str_version()))

    def cancel_release(self, is_master=False):
        messages.warning("Not implemented yet")

    """
    Hotfix methods
    """
    def start_hotfix(self):
        """Open an application release"""
        self._pull_repository()

        # Change version
        self.version["hotfix"] += 1

        create_hotfix = messages.question("Validate this hotfix name -> hotfix/{}? [y/n] ".format(
            self._str_version()))
        if create_hotfix.lower() != "y":
            messages.warning("Quitting...")
            sys.exit(errno.ENOMSG)

        # Create remote and local branch
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        response = session.get("{}/api/v3/repos/{}/git/refs/heads".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers)

        if response.status_code != 200:
            messages.critical("An error occurred while retrieving refs.")
            return False

        commit_ref = None
        for item in response.json():
            if item["ref"] == "refs/heads/master":
                commit_ref = item["object"]["sha"]
                break

        if not commit_ref:
            messages.critical("master branch was not found on remote repository.")
            return False

        payload = {
            "ref": "refs/heads/hotfix/{}".format(self._str_version()),
            "sha": commit_ref
        }

        response = session.post("{}/api/v3/repos/{}/git/refs".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New branch: hotfix/{} created".format(self._str_version()))

            if self._pull_branch("hotfix/{}".format(self._str_version()), create_branch=True):
                messages.success("Switched to a new branch \"hotfix/{}\".".format(self._str_version()))

                with sarge.Capture() as output:
                    self._set_version()
                    sarge.run("git add version &&"
                              "git commit -m \"Update version to {}\" &&"
                              "git push origin hotfix/{}".format(self._str_version(), self._str_version()),
                              stdout=output,
                              stderr=output)
                return True

            else:
                messages.critical("Unable to checkout to branch: hotfix/{}".format(self._str_version()))
                return False

        elif response.status_code == 422:
            messages.error("Feature branch hotfix/{} already exists.".format(self._str_version()))
            return False

        else:
            messages.critical("Release branch hotfix/{} can not be created ({}: {}).".format(
                self._str_version(),
                response.status_code,
                response.json()["message"]))
            return False

    def review_hotfix(self):
        output = sarge.run("git checkout hotfix/{}".format(self._str_version()),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.error("No hotfix found")
            return False

        self._push_branch("hotfix/{}".format(self._str_version()))

        # Create a Pull Request
        session = requests.Session()

        headers = {
            "Authorization": "token {}".format(self.glow_config.get("github", "token")),
            "Content-Type": "application/json"
        }

        branch_from = "master"
        branch_to = "hotfix/{}".format(self._str_version())

        changelog = self._generate_changelog(branch_from, branch_to)

        if not changelog:
            return False

        payload = {
            "title": "Hotfix {}".format(self._str_version()),
            "body": changelog,
            "head": branch_to,
            "base": branch_from,
        }

        response = session.post("{}/api/v3/repos/{}/pulls".format(
            self.glow_config.get("github", "url"),
            self.glow_config.get("github", "repository_name")),
            headers=headers,
            data=json.dumps(payload))

        if response.status_code == 201:
            messages.success("New Pull Request created: {}".format(response.json()["html_url"]))
            return True

        else:
            messages.critical(response.json()["message"])
            for error in response.json()["errors"]:
                messages.error(error["message"])
            return False

    def finish_hotfix(self):
        self._pull_repository()

        output = sarge.run("git show master\^1",
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to find previous commit on \"master\" branch.")
            return False

        commit_ref = output.stdout.text.split("\n")[0].replace("commit ", "")
        changelog = self._generate_changelog(commit_ref, "master")

        if not changelog:
            return False

        messages.info("Tag version {}.".format(self._str_version()))
        output = sarge.run("git tag -a {} -m \"{}\"".format(
            self._str_version(),
            changelog.replace("\"", "\\\"")),
            stdout=sarge.Capture(),
            stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to tag version {}.".format(self._str_version()))
            return False

        messages.info("Merge tag \"{}\" into \"develop\".".format(self._str_version()))
        merge_message = "Merge tag \"{}\" into \"develop\"\n\n{}".format(self._str_version(), changelog)
        output = sarge.run("git push origin --tags && "
                           "git checkout develop && "
                           "git merge --no-ff {} -m \"{}\" -X theirs".format(self._str_version(), merge_message),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.critical("Unable to merge tag into \"develop\"")
            return False

        self._push_branch("develop")

        output = sarge.run("git branch -d hotfix/{} &&"
                           "git push origin :hotfix/{}".format(self._str_version(), self._str_version()),
                           stdout=sarge.Capture(),
                           stderr=sarge.Capture())

        if output.returncode > 0:
            messages.warning("Unable to remove hotfix branches.")
            return False

        messages.success("Hotfix {} finished.".format(self._str_version()))

    def cancel_hotfix(self):
        messages.warning("Not implemented yet")

    """Main"""
    def main(self):
        parser = argparse.ArgumentParser(description="Github for git-flow helpers")
        parser.add_argument("action")
        parser.add_argument("entity")
        parser.add_argument("key", nargs="?", default=None)
        parser.add_argument("extras", nargs="*", default=None)
        parser.add_argument("--master", action="store_true")

        args = parser.parse_args()

        methods_list = [func for func in dir(self) if callable(getattr(self, func)) and not func.startswith("_")]
        method_name = "{}_{}".format(args.action, args.entity)

        if method_name not in methods_list:
            messages.error("Unknown command \"{} {}\"".format(args.action, args.entity))
            sys.exit(1)

        _func = getattr(self, method_name)

        if "feature" in method_name:
            _func(args.key, "-".join(args.extras).lower())
        elif "release" in method_name:
            _func(args.master)
        else:
            _func()


if __name__ == "__main__":
    glow = Flhub()
    glow.main()
