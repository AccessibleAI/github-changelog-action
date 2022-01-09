import argparse
from datetime import date
import requests
import re
import subprocess
import os

parser = argparse.ArgumentParser(description='Create release notes.')
parser.add_argument('--from-version', metavar='From Version', type=str,
                    help='The version to start from')
parser.add_argument('--to-version', metavar='To Version', type=str,
                    help='The new version')
parser.add_argument('--jira-token', metavar='JiraToken',nargs='?', type=str)
class FixVersion:
    def __init__(self, name):
        self.name = name
        self.tickets = []
        self.epic_tickets = []

    def add_ticket(self, ticket):
        if ticket.issueType == "Epic":
            self.epic_tickets.append(ticket)
        else:
            self.tickets.append(ticket)

    def has_epics(self):
        if self.name == "master":
            return False
        return len(self.epic_tickets) > 0

    def __str__(self):
        return "Fix version {}. has {} tickets, and {} epics".format(self.name, len(self.tickets), len(self.epic_tickets))


class Ticket:
    def __init__(self, data):
        self.key = data["key"]
        self.number = int(self.key.split("-")[1])
        self.issueType = data["fields"]["issuetype"]["name"]
        self.issueTypeVal = Ticket.issue_type_val(self.issueType)
        self.summary = data["fields"]["summary"]
        self.description = data["fields"]["description"]
        self.fix_versions = list(map(lambda x: str(x["name"]), data["fields"]["fixVersions"])) or []
        self.fix_version = "master"
        if "master" in self.fix_versions:
            self.fix_version = "master"
        elif len(self.fix_versions) > 0:
            self.fix_version = self.fix_versions[0]

    def __lt__(self, other):
        if self.fix_version != other.fix_version:
            return self.fix_version < other.fix_version
        if self.issueTypeVal != other.issueTypeVal:
            return self.issueTypeVal < other.issueTypeVal
        else:
            return self.number < other.number

    def __str__(self):
        if self.issueType == "Epic":
            return "{} - {}: {}\n{}".format(self.key, self.issueType, self.summary, self.description)
        else:
            return "{} - {}: {}".format(self.key, self.issueType, self.summary)

    def print_without_key(self):
        if self.issueType == "Bug":
            self.issueType = "Fix"
        if self.issueType == "Epic":
            return "{}: {}\n{}".format(self.issueType, self.summary, self.description)
        else:
            return "{}: {}".format(self.issueType, self.summary)

    def issue_type_val(issueType):
        if issueType == 'Epic':
            return 3
        elif issueType == 'Task':
            return 4
        elif issueType == 'New Feature':
            return 3
        elif issueType == 'Improvment':
            return 4
        elif issueType == 'Bug':
            return 5
        elif issueType == 'Sub-task':
            return 7
        else:
            return 7

def get_fix_version_epics(fix_version_name, jira_token):
    url = "https://cnvrgio.atlassian.net/rest/api/2/search?jql=issuetype%20%3D%20Epic%20AND%20fixVersion%20%3D%20{}%20AND%20project%20%3D%20%22DEV%22%20&maxResults=80".format(fix_version_name)
    payload={}
    headers = {
      'Authorization': jira_token
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.ok:
        return response.json()
    else:
        return None

def get_ticket_data(ticket_number, jira_token):
    url = "https://cnvrgio.atlassian.net/rest/api/latest/issue/{}".format(ticket_number)
    payload={}
    headers = {
      'Authorization': jira_token
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.ok:
        return response.json()
    else:
        return None

def create_tickets(tickets_numbers, jira_token):
    tickets = []
    for ticket_number in tickets_numbers:
        try:
            data = get_ticket_data(ticket_number, jira_token)
            ticket = Ticket(data)
            tickets.append(ticket)
        except Exception as e:
            print(e)
            print("failed to get ticket data {}".format(ticket_number))
    tickets.sort(reverse=True)
    return tickets

def run_git_command(command):
    bashCommand = command
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE, encoding='UTF-8')
    output, error = process.communicate()
    return str(output.strip())

def set_env_var(name,value):
    run_git_command(f"echo {name}={value} >> $GITHUB_ENV")

def get_all_commits_messages_since_tag(from_version,to_version):
    if run_git_command("git tag -l {}".format(from_version)) == "":
        from_version = "origin/{}".format(from_version)
        to_version = "origin/{}".format(to_version)
    from_version_rev = run_git_command("git rev-parse {}".format(from_version))
    to_version_rev = run_git_command("git rev-parse {}".format(to_version))
    messages = run_git_command("git log {}..{}  --pretty=format:'%s'".format(from_version_rev,to_version_rev))
    messages = messages.splitlines()
    messages = list(set(messages)) # Filter duplicates
    return messages

def get_all_tickets_from_messages(all_commit_messages):
    tickets = {}
    for message in all_commit_messages:
        ticket_re = re.search("([A-Za-z]{1,5}-\\d+)", message)
        if ticket_re:
            ticket = ticket_re.group()
            tickets[ticket] = True
    return tickets.keys()

def create_release_notes_str(fix_versions_hash):
    rn = ""

    for fix_version_name in fix_versions_hash:
        fixVersion = fix_versions_hash[fix_version_name]
        if fixVersion.has_epics():
            for ticket in fixVersion.epic_tickets:
                rn += "\n* {}".format(ticket)
            for ticket in fixVersion.tickets:
                if ticket.issueTypeVal < 5:
                    rn += "\n* {}".format(ticket)
        else:
            for ticket in fixVersion.tickets:
                rn += "\n* {}".format(ticket)
    return rn

def create_release_notes_str_without_key(fix_versions_hash):
    rn = ""

    for fix_version_name in fix_versions_hash:
        fixVersion = fix_versions_hash[fix_version_name]
        if fixVersion.has_epics():
            for ticket in fixVersion.epic_tickets:
                rn += "\n* {}".format(ticket.print_without_key())
            for ticket in fixVersion.tickets:
                if ticket.issueTypeVal < 5:
                    rn += "\n* {}".format(ticket.print_without_key())
        else:
            for ticket in fixVersion.tickets:
                if ticket.issueType != "Task":
                    rn += "\n* {}".format(ticket.print_without_key())
    return rn

def add_to_rn_file(rn,file="Readme.md"):
    with open(file, "w") as rn_file:
        rn_file.write(rn)

def build_fix_versions_hash(tickets):
    fix_versions_hash = {}
    for ticket in tickets:
        fix_version = ticket.fix_version
        if not fix_version in fix_versions_hash:
            fix_versions_hash[fix_version] = FixVersion(fix_version)
        fix_versions_hash[fix_version].add_ticket(ticket)
    return fix_versions_hash

def add_epics_to_fix_versions(fix_versions_hash, jira_token):
    try:
        for fix_version_name in fix_versions_hash:
            fixVersion = fix_versions_hash[fix_version_name]
            if fixVersion.name == "master":
                continue
            res = get_fix_version_epics(fixVersion.name, jira_token)
            issues = res["issues"]
            for t in issues:
                ticket = Ticket(t)
                fixVersion.add_ticket(ticket)
    except Exception as e:
        print(e)

if __name__ == '__main__':

    args = parser.parse_args()
    from_version = args.from_version
    to_version = args.to_version
    jira_token=args.jira_token
    all_commit_messages = get_all_commits_messages_since_tag(from_version,to_version)
    tickets_numbers = get_all_tickets_from_messages(all_commit_messages)
    tickets = create_tickets(tickets_numbers, jira_token)
    fix_versions_hash = build_fix_versions_hash(tickets)
    add_epics_to_fix_versions(fix_versions_hash, jira_token)

    rn = create_release_notes_str(fix_versions_hash)
    rn2 = create_release_notes_str_without_key(fix_versions_hash)
    file = '/tmp/release_notes.txt'
    file2 = '/tmp/release_notes_without_issues.txt'
    add_to_rn_file(rn,file)
    add_to_rn_file(rn2,file2)
    print(f"::set-output name=change_log_file::{file}")
    print(f"::set-output name=change_log_file_without_issues::{file2}")
    if 'dev' in rn.lower():
        print("::set-output name=empty::false")
    else:
        print("::set-output name=empty::true")