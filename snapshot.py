#!/usr/bin/env python

from datetime import datetime
import argparse
import boto3
import sys
import time
from prometheus_client import start_http_server, Summary
from prometheus_client import Gauge

class ebs_snapshot:
    def __init__(self, args):

        self.__debug     = args.debug
        self.__profile   = args.profile
        self.__region    = args.region
        self.__pattern   = args.pattern
        self.__threshold = args.threshold
        self.__exporter  = args.exporter
        self.__g_snapshot_count = Gauge('ebs_snapshot_count', 'number of snapshots found',['pattern'])
        self.__g_snapshot_age = Gauge('ebs_snapshot_age', 'age of the lastet ' +self.__pattern + ' snapshot',['pattern'])
        self.__g_snapshot_progress = Gauge('ebs_snapshot_progress', 'progress of the lastet snapshot [%] ' +self.__pattern + ' snapshot',['pattern'])
        self.__connect_and_check()

    def __connect_and_check(self):
        session = boto3.session.Session(
                profile_name = self.__profile,
                region_name  = self.__region
                )

        self.__snaps = []

        self.out_status = 0
        self.out_msg = 'OK: snapshot up-to-date'

        self.__ec2_client = session.client('ec2')
        self.__get_snapshots()
        self.__check_status()


    def __print(self, string, level=1):
        '''
        Simple "print" wrapper: sends to stdout if debug is > 0
        '''
        if level <= self.__debug:
            print (string)

    def __get_snapshots(self):
        '''
        Get snapshots, filter on PATTERN value. Also replace TODAY if present.
        '''
        self.__print('Getting snapshots')
        today = time.strftime('%A')
        pattern = self.__pattern.replace('TODAY', today)
        self.__print('Filter snapshots with %s'%pattern)

        self.__snaps = self.__ec2_client.describe_snapshots(
                Filters=[
                    {
                        'Name': 'description',
                        'Values': [
                            pattern
                            ],
                        }
                    ]
                )
        self.__print('There are %i snapshots matching the pattern' % len(self.__snaps['Snapshots']))

    def __check_status(self):
        self.__g_snapshot_count.labels(self.__pattern).set( len(self.__snaps['Snapshots']))
        if len(self.__snaps['Snapshots']) == 0:
            self.out_status = 2
            self.out_msg    = 'CRITICAL: no snapshot for "%s"' % self.__pattern
        elif len(self.__snaps['Snapshots']) > 1:
            self.out_status = 3
            self.out_msg    = 'UNKNOWN: more than one snapshot for "%s", unable to parse' % self.__pattern
        else:
            snap = self.__snaps['Snapshots'][0]
            snap_age = (datetime.utcnow() - snap['StartTime'].replace(tzinfo=None)).total_seconds() / 3600
            self.__g_snapshot_age.labels(self.__pattern).set(snap_age)
            progress = snap['Progress']
            self.__g_snapshot_progress.labels(self.__pattern).set(float(progress.strip('%')))
            if snap_age >= 24*7+2:
                self.out_status = 2
                self.out_msg    = 'CRITICAL: no current snapshot for "%s" (%.1d days old)' % (self.__pattern, snap_age/24)
            elif progress != '100%' and snap_age < 5:
                self.out_status = 0
                self.out_msg    = 'OK: snapshot in progress (%s)' % progress['Progress']
            elif snap['StartTime'].date() != datetime.today().date() and datetime.today().hour > self.__threshold:
                self.out_status = 2
                self.out_msg    = 'CRITICAL: no current snapshot for "%s" (%.1d days old)' % (self.__pattern, snap_age/24)
            else:
                self.out_status = 0
                self.out_msg = 'OK: snapshot up-to-date'

    REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
    # Decorate function with metric.
    @REQUEST_TIME.time()
    def process_request(self, t):
        """check is done here"""
        self.__connect_and_check()
        time.sleep(t)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check if a current snapshot exists')
    parser.add_argument('--debug',  '-d',   help='Set verbosity level', default=0, type=int)
    parser.add_argument('--profile', '-p', help='Pass AWS profile name', default='default')
    parser.add_argument('--region', '-r',   help='Set AWS region', default='eu-west-1')
    parser.add_argument('--pattern', '-P', help='Matches Description field for snapshots. You might use TODAY as keyword.', required=True)
    parser.add_argument('--threshold', '-t', help='Delay after which we expect the volume to be available, in hours.', default='4', type=int)
    parser.add_argument('--exporter',  help='run as prometheus exporter on default port 8080 ', action='store_const', const=True)
    parser.add_argument('--exporter_port',  help='if run as prometheus exporter on default port 8080, change port here ', default=8080, type=int)
    parser.add_argument('--scrape_delay',  help='how many seconds between aws api scrape', default=4, type=int)


    args = parser.parse_args()

    worker = ebs_snapshot(args)
    if args.exporter:
        print("exporter mode on port %i"% args.exporter_port)
        start_http_server(args.exporter_port)
        while True:
            worker.process_request(args.scrape_delay)
    else:
        print(worker.out_msg)
        sys.exit(worker.out_status)
