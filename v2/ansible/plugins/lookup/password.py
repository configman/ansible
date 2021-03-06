# (c) 2012, Daniel Hokka Zakrisson <daniel@hozac.com>
# (c) 2013, Javier Candeira <javier@candeira.com>
# (c) 2013, Maykel Moya <mmoya@speedyrails.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

import os
import errno
import string
import random

from string import ascii_letters, digits

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.utils.encrypt import do_encrypt

DEFAULT_LENGTH = 20

class LookupModule(LookupBase):

    def random_password(self, length=DEFAULT_LENGTH, chars=C.DEFAULT_PASSWORD_CHARS):
        '''
        Return a random password string of length containing only chars.
        NOTE: this was moved from the old ansible utils code, as nothing
              else appeared to use it.
        '''

        password = []
        while len(password) < length:
            new_char = os.urandom(1)
            if new_char in chars:
                password.append(new_char)

        return ''.join(password)

    def random_salt(self):
        salt_chars = ascii_letters + digits + './'
        return self.random_password(length=8, chars=salt_chars)

    def run(self, terms, variables, **kwargs):

        ret = []

        if not isinstance(terms, list):
            terms = [ terms ]

        for term in terms:
            # you can't have escaped spaces in yor pathname
            params = term.split()
            relpath = params[0]

            paramvals = {
                'length': DEFAULT_LENGTH,
                'encrypt': None,
                'chars': ['ascii_letters','digits',".,:-_"],
            }

            # get non-default parameters if specified
            try:
                for param in params[1:]:
                    name, value = param.split('=')
                    assert(name in paramvals)
                    if name == 'length':
                        paramvals[name] = int(value)
                    elif name == 'chars':
                        use_chars=[]
                        if ",," in value: 
                            use_chars.append(',')
                        use_chars.extend(value.replace(',,',',').split(','))
                        paramvals['chars'] = use_chars
                    else:
                        paramvals[name] = value
            except (ValueError, AssertionError) as e:
                raise AnsibleError(e)

            length  = paramvals['length']
            encrypt = paramvals['encrypt']
            use_chars = paramvals['chars']

            # get password or create it if file doesn't exist
            path = self._loader.path_dwim(relpath)
            if not os.path.exists(path):
                pathdir = os.path.dirname(path)
                if not os.path.isdir(pathdir):
                    try:
                        os.makedirs(pathdir, mode=0700)
                    except OSError as e:
                        raise AnsibleError("cannot create the path for the password lookup: %s (error was %s)" % (pathdir, str(e)))

                chars = "".join([getattr(string,c,c) for c in use_chars]).replace('"','').replace("'",'')
                password = ''.join(random.choice(chars) for _ in range(length))

                if encrypt is not None:
                    salt = self.random_salt()
                    content = '%s salt=%s' % (password, salt)
                else:
                    content = password
                with open(path, 'w') as f:
                    os.chmod(path, 0600)
                    f.write(content + '\n')
            else:
                content = open(path).read().rstrip()
                sep = content.find(' ')

                if sep >= 0:
                    password = content[:sep]
                    salt = content[sep+1:].split('=')[1]
                else:
                    password = content
                    salt = None

                # crypt requested, add salt if missing
                if (encrypt is not None and not salt):
                    salt = self.random_salt()
                    content = '%s salt=%s' % (password, salt)
                    with open(path, 'w') as f:
                        os.chmod(path, 0600)
                        f.write(content + '\n')
                # crypt not requested, remove salt if present
                elif (encrypt is None and salt):
                    with open(path, 'w') as f:
                        os.chmod(path, 0600)
                        f.write(password + '\n')

            if encrypt:
                password = do_encrypt(password, encrypt, salt=salt)

            ret.append(password)

        return ret

