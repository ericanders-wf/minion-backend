# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import requests
import unittest

from flask import Flask, make_response, redirect, url_for
from collections import namedtuple
from base import TestPluginBaseClass, test_app
from minion.plugins.basic import RobotsPlugin
from multiprocessing import Process

@test_app.route('/robots.txt')
def robot():
    return redirect(url_for('static', filename='robots.txt'))

bad_robot_app= Flask(__name__)
@bad_robot_app.route('/robots.txt')
def bad_robots():
    return redirect(url_for('static', filename='bad-robots.txt'))

no_robot_app = Flask(__name__)
@no_robot_app.route('/')
def home():
    res = make_response()
    return res


class TestRobotsPlugin(TestPluginBaseClass):
    __test__ = True

    @classmethod
    def setUpClass(cls):
        """ We have to launch three ports in order to test this plugin. """

        _apps = {
                    "good_robot_app": test_app,
                    "bad_robot_app": bad_robot_app,
                    "no_robot_app": no_robot_app
                }

        def run_app(port, name):
            _app = _apps[name]
            _app.run(host='localhost', port=port)

        cls.server1 = Process(target=run_app, args=(1234, 'good_robot_app',))
        cls.server2 = Process(target=run_app, args=(1235, 'bad_robot_app',))
        cls.server3 = Process(target=run_app, args=(1236, 'no_robot_app',))
        cls.server1.daemon = True
        cls.server2.daemon = True
        cls.server3.daemon = True
        cls.server1.start()
        cls.server2.start()
        cls.server3.start()

        cls.pname = "RobotsPlugin"
        cls.Issue = namedtuple('Issue', 'code summary severity')
        cls.Robots = RobotsPlugin()

    @classmethod
    def tearDownClass(cls):
        cls.server1.terminate()
        cls.server2.terminate()
        cls.server3.terminate()

    def _get_summary(self, key, fill_with=None):
        _summary = self.Robots.REPORTS[key]['Summary']
        if fill_with:
            return _summary.format(**fill_with)
        else:
            return _summary

    def _run(self, base="http://localhost:1234", api="/test"):
        runner_resp = self.run_plugin(self.pname, base + api)
        return runner_resp

    def _get_issues(self, resps):
        issues = []
        for issue in resps:
            if issue.get('data') and issue['data'].get('Code'):
                _issue = self.Issue(issue['data']['Code'],
                                    issue['data']['Summary'],
                                    issue['data']['Severity'])
                issues.append(_issue)
        return issues

    def _test_expecting_codes(self, issues, expects, message):
        self.assertEqual(len(issues), len(expects), msg=message)
        for expect in expects:
            self._test_expecting_code(issues, expect, message)

    def _test_expecting_code(self, issues, expect, message):
        codes = [issue.code for issue in issues]
        self.assertEqual(True, expect in codes, msg=message)

    def test_valid_robots_file(self):
        # first, assert that the plugin can assert the file from direct link
        resp = self._run(base="http://localhost:1234", api="/robots.txt")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-0'],
            "Expecting found robots.txt and validated")

        # next, assert plugin can ignore paths and make the direct link on its own
        resp = self._run(base="http://localhost:1234", api="/")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-0'],
            "Expecting found robots.txt and validated")

    def test_missing_robots_file(self):
        resp = self._run(base="http://localhost:1236", api="/robots.txt")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-1'],
            "Robots.txt is not found.")

        # like valid robots, plugin should make the direct link on its own
        resp = self._run(base="http://localhost:1236", api="/")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-1'],
            "Robots.txt is not found.")

    def test_invalid_robots_file(self):
        resp = self._run(base="http://localhost:1235", api="/robots.txt")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-2'],
            "Expecting invalid robots.txt detected")

        # like valid robots, plugin should make the direct link on its own
        resp = self._run(base="http://localhost:1235", api="/")
        issues = self._get_issues(resp)
        self._test_expecting_codes(
            issues,
            ['ROBOTS-2'],
            "Expecting invalid robots.txt detected")
