from pygit2 import Repository, GIT_BLAME_TRACK_COPIES_SAME_FILE, GIT_SORT_TOPOLOGICAL, GIT_SORT_REVERSE

def get_first_latest_modification(filepath):
  repo = Repository('.git')
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
