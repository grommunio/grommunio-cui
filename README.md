# grommunio CUI

![project license](https://img.shields.io/badge/license-AGPL--3.0-orange)
[![latest version](https://shields.io/github/v/tag/grommunio/grommunio-cui)](https://github.com/grommunio/grommunio-cui/tags)
[![scrutinizer](https://img.shields.io/scrutinizer/build/g/grommunio/grommunio-cui)](https://scrutinizer-ci.com/g/grommunio/grommunio-cui/)
[![code size](https://img.shields.io/github/languages/code-size/grommunio/grommunio-cui)](https://github.com/grommunio/grommunio-cui)

[![pull requests welcome](https://img.shields.io/badge/PRs-welcome-ff69b4.svg)](https://github.com/grommunio/grommunio-cui/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
[![code with love by grommunio](https://img.shields.io/badge/%3C%2F%3E%20with%20%E2%99%A5%20by-grommunio-ff1414.svg)](https://grommunio.com)
[![twitter](https://img.shields.io/twitter/follow/grommunio?style=social)](https://twitter.com/grommunio)

**grommunio CUI (console user interface) is a text-based interface for managing the basic grommunio Appliance configuration.**

<details open="open">
<summary>Overview</summary>

- [About](#about)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Status](#status)
- [Support](#support)
- [Project assistance](#project-assistance)
- [Contributing](#contributing)
  - [Additional notes](#additional-notes)
- [Security](#security)
- [Translators](#translators)
- [License](#license)

</details>

---

## About grommunio CUI

- **Simple** and basic configuration of the grommunio Appliance
- **Easy to use**, with a console interface with natural console behavior
- **Localized**, with selectable keyboard layouts and languages

The primary use for grommunio CUI is for simple management of the grommunio Appliance. Support for manual installations is planned and will surface in the future.

## Getting Started

### Prerequisites

For CUI to work properly, the Python modules from **[requirements.txt](requirements.txt)** need to be installed

### Installation

Make sure the path is correctly set:

```
export PYTHONPATH="$PYTHONPATH:<cui_source_dir>"
```

or let the install script copy cui.sh to the system:

```
./install.sh
```

## Status

- [Top Feature Requests](https://github.com/grommunio/grommunio-cui/issues?q=label%3Aenhancement+is%3Aopen+sort%3Areactions-%2B1-desc) (Add your votes using the 👍 reaction)
- [Top Bugs](https://github.com/grommunio/grommunio-cui/issues?q=is%3Aissue+is%3Aopen+label%3Abug+sort%3Areactions-%2B1-desc) (Add your votes using the 👍 reaction)
- [Newest Bugs](https://github.com/grommunio/grommunio-cui/issues?q=is%3Aopen+is%3Aissue+label%3Abug)

## Support

- Support is available through **[grommunio GmbH](https://grommunio.com)** and its partners.
- grommunio CUI community is available here: **[grommunio Community](https://community.grommunio.com)**

For direct contact to the maintainers (for example to supply information about a security-related responsible disclosure), you can contact grommunio directly at [dev@grommunio.com](mailto:dev@grommunio.com)

## Project assistance

If you want to say **thank you** or/and support active development of grommunio CUI:

- Add a [GitHub Star](https://github.com/grommunio/grommunio-cui) to the project.
- Tweet about grommunio CUI.
- Write interesting articles about the project on [Dev.to](https://dev.to/), [Medium](https://medium.com/), your personal blog or any medium you feel comfortable with.

Together, we can make grommunio CUI **better**!

## Contributing

First off, thanks for taking the time to contribute! Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make will benefit everybody else and are **greatly appreciated**.

If you have found an issue and want to report an issue, either reach out to us in our [community](https://community.grommunio.com), or, if you have a subscription, open up a [support case](https://grommunio.com/).

To provide changesets,

- Clone the repository from https://github.com/grommunio/grommunio-cui.git
- Commit and sign your work (```git commit -s```).

Then, either

- create a pull request towards the master branch.

or

- upload commits to a git store of your choosing, or export the series as a patchset using [git format-patch](https://git-scm.com/docs/git-format-patch).
- send the patch(es) or git link to [dev@grommunio.com](mailto:dev@grommunio.com) and we will consider the submission.

### Additional notes

- If possible, please only work on one issue per commit.

## Security

grommunio CUI follows good practices of security. grommunio constantly monitors security-related issues.
grommunio CUI is provided **"as is"** without any **warranty**. For professional support options through subscriptions, head over to [grommunio](https://grommunio.com).

## Translators

First use xgettext from the package `gettext-tools` and use it to search for `T_`-function calls and generate the template pot file via:

```
xgettext -kT_ -d cui -o locale/cui.pot cui/*.py
```

and then use `msgmerge` to merge the new or changed keys into the corresponding language file.

```
for lang in $(cd locale && echo */); do \
	msgmerge --update locale/$lang/LC_MESSAGES/cui.po locale/cui.pot; \
done
``

Now handover the corresponding po-files to the translator with the modified language keys. After including the translation changes you will have to reformat the binary mo-files with the assist of the translated po-files.

```    
for lang in $(cd locale && echo */); do \
	msgfmt -o locale/$lang/LC_MESSAGES/cui.mo locale/$lang/LC_MESSAGES/cui.po; \
done
```

## License

This project is licensed under the **GNU Affero General Public License v3**.

See [LICENSE.txt](LICENSE.txt) for more information.
