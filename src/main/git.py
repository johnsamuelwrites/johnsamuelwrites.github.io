#
# SPDX-FileCopyrightText: 2020 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

from pygit2 import (
    Repository,
    GIT_BLAME_TRACK_COPIES_SAME_FILE,
    GIT_SORT_TOPOLOGICAL,
    GIT_SORT_REVERSE,
)


def get_first_latest_modification(filepath, main_directory="./"):
    repo = Repository(main_directory + ".git")
    latest = None
    first = None
    blame = repo.blame(filepath, flags=GIT_BLAME_TRACK_COPIES_SAME_FILE)
    for b in blame:
        commit = repo.get(b.final_commit_id)
        if not latest:
            latest = commit.commit_time
        elif latest < commit.commit_time:
            latest = commit.commit_time

        if not first:
            first = commit.commit_time
        elif first > commit.commit_time:
            first = commit.commit_time
    return first, latest


def get_modification_list(filepath, main_directory="./"):
    repo = Repository(main_directory + ".git")
    latest = None
    first = None
    blame = repo.blame(filepath, flags=GIT_BLAME_TRACK_COPIES_SAME_FILE)
    modifications = list()
    for b in blame:
        commit = repo.get(b.final_commit_id)
        modifications.append(
            (
                commit.author.name,
                commit.id,
                commit.short_id,
                commit.commit_time,
                commit.commit_time_offset,
                commit.message,
            )
        )

    return modifications
