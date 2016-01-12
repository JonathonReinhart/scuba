def passwd_entry(**kw):
    return '{username}:{password}:{uid}:{gid}:{gecos}:{homedir}:{shell}'.format(**kw)

def group_entry(groupname, password, gid, users=[]):
    return '{groupname}:{password}:{gid}:{users}'.format(
            groupname = groupname,
            password = password,
            gid = gid,
            users = ','.join(users))

def shadow_entry(username, **kw):
    return '{username}:{password}:{lstchg}:{minchg}:{maxchg}:{warn}:{inact}:{expire}:{flag}'.format(
            username = username,
            password = kw.get('password', '*'),
            lstchg = kw.get('lstchg', ''),
            minchg = kw.get('minchg', ''),
            maxchg = kw.get('maxchg', ''),
            warn = kw.get('warn', ''),
            inact = kw.get('inact', ''),
            expire = kw.get('expire', ''),
            flag = '',
            )

