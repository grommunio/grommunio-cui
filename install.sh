#!/bin/bash
target="/usr/local/bin/"
file='cui.sh'
tmp='./tmp/'

userid=$(id -u)

if [ -n "$(which zypper)" ]; then
  cmd="zypper"
elif [ -n "$(which apt-get)" ]; then
  cmd="apt-get"
else
  cmd="apt"
fi

if [ $userid -eq 0 ]; then
  echo "Checking for pip ..."
  if [ -z "$(which pip)" ]; then
    read -p "pip is not installed! Shell I do for you? (y/n)" answer
    if [ "$answer" == "y" ]; then
      sudo $cmd install python-pip
    else
      echo "Aborting."
      exit 1
    fi
  fi
  if [ -z "$(which pip3)" ]; then
    read -p "pip3 is not installed! Shell I do for you? (y/n)" answer
    if [ "$answer" == "y" ]; then
      sudo $cmd install python3-pip
    else
      echo "Aborting."
      exit 1
    fi
  fi

  echo "Installing Urwid"
  cd /opt/
  git clone https://github.com/urwid/urwid.git
  cd -

  echo "Installing python packages ..."
  [ -d "$tmp" ] || mkdir -p "$tmp"

  [ -r 'requirements.txt' ] && sudo pip install -r requirements.txt
  [ -r 'requirements.txt' ] && sudo pip3 install -r requirements.txt

  echo "Creating script ..."

  echo '#!/bin/bash' > "${tmp}/${file}"
  echo >> "${tmp}/${file}"
  echo "export PYTHONPATH=\"\$PYTHONPATH:/opt/urwid:$(pwd)\"" >> "${tmp}/${file}"
  echo >> "${tmp}/${file}"
  echo "python3 $(pwd)/cui/__init__.py \$@" >> "${tmp}/${file}"
  echo >> "${tmp}/${file}"

  echo "Installing ${tmp}/${file} to ${target}"

  chmod 755 "${tmp}/${file}"

  cp "${tmp}/${file}" "${target}"
else
  echo "You have to be superuser."
fi
echo "Bye."
