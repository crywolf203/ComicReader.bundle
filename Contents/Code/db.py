import os
import hashlib
import utils
import archives


def retrieve_username(token):
    """retrieve the username for the given access token from plex.tv"""
    access_tokens = XML.ElementFromURL(
        'https://plex.tv/servers/{}/access_tokens.xml?auth_token={}'.format(
            Core.get_server_attribute('machineIdentifier'), os.environ['PLEXTOKEN']),
        cacheTime=CACHE_1HOUR)
    for child in access_tokens.getchildren():
        if child.get('token') == token:
            username = child.get('username')
            return username if username else child.get('title')
    return token


class DictDB(object):

    def __init__(self):
        Dict['_load'] = True
        self.version = '1.0.0'
        if 'db_version' in Dict:
            self.version = Dict['db_version']

    def ensure_keys(self):
        Dict['_load'] = True
        if 'usernames' not in Dict:
            Dict['usernames'] = {}
        if 'read_states' not in Dict:
            Dict['read_states'] = {}

    def get_user(self, token):
        h = hashlib.sha1(token).hexdigest()
        try:
            if h in Dict['usernames']:
                user = Dict['usernames'][h]
            else:
                Dict['usernames'][h] = retrieve_username(token)
                Dict.Save()
                user = Dict['usernames'][h]
        except Exception as e:
            Log.Error('get_session_identifier: {}'.format(e))
            user = h
        if user not in Dict['read_states']:
            Dict['read_states'][user] = {}
        return user

    def get_state(self, user, archive_path):
        key = unicode(archive_path)
        if user not in Dict['read_states'] or key not in Dict['read_states'][user]:
            cur, total = (-1, -1)
        else:
            cur, total = Dict['read_states'][user][key]
        if total <= 0:
            a = archives.get_archive(archive_path)
            total = len(a.namelist())
        return (int(cur), int(total))

    def set_state(self, user, archive_path, page):
        cur_page, total_pages = self.get_state(user, archive_path)
        try:
            Dict['read_states'][user][unicode(archive_path)] = (page, total_pages)
        except Exception:
            Log.Error('unable to write state.')
        else:
            Dict.Save()

    def read(self, user, archive_path, fuzz=5):
        cur, total = self.get_state(user, archive_path)
        if cur < 0 or total < 0:
            return utils.State.UNREAD
        return utils.State.READ if abs(total - cur) < fuzz else utils.State.IN_PROGRESS

    def mark_read(self, user, archive_path):
        state = self.get_state(user, archive_path)
        new_state = (state[1], state[1])
        Dict['read_states'][user][unicode(archive_path)] = new_state
        Dict.Save()

    def mark_unread(self, user, archive_path):
        try:
            del Dict['read_states'][user][unicode(archive_path)]
        except Exception as e:
            Log.Error('could not mark unread. {}'.format(str(e)))
        else:
            Dict.Save()

    def comic_state(self, user, archive_path, fuzz=5):
        key = unicode(archive_path)
        if user not in Dict['read_states'] or key not in Dict['read_states'][user]:
            return utils.State.NONE
        else:
            cur, total = Dict['read_states'][user][key]
        return utils.State.READ if abs(total - cur) < fuzz else utils.State.IN_PROGRESS

    def series_state(self, user, directory):
        states = set([
            (self.series_state(user, os.path.join(directory, x)) if is_dir else
             self.comic_state(user, os.path.join(directory, x)))
            for x, is_dir in utils.filtered_listdir(directory)
        ])
        if not states:
            return utils.State.NONE
        return states.pop() if len(states) == 1 else utils.State.IN_PROGRESS


DATABASE = DictDB()