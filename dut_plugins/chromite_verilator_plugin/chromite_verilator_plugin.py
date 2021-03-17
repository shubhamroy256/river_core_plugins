# See LICENSE for details

import os
import sys
import pluggy
import shutil
import random
import re
import datetime
import pytest
import glob

from river_core.log import logger
from river_core.utils import *

dut_hookimpl = pluggy.HookimplMarker('dut')


class ChromitePlugin(object):
    '''
        Plugin to set chromite as the target
    '''
    @dut_hookimpl
    def init(self, ini_config, test_list, work_dir):
        self.name = 'chromite'
        logger.debug('Pre Compile Stage')

        # Get plugin specific configs from ini
        self.jobs = ini_config['jobs']

        self.filter = ini_config['filter']

        self.riscv_isa = ini_config['isa']
        if '64' in self.riscv_isa:
            self.xlen = 64
        else:
            self.xlen = 32
        self.elf = 'dut.elf'

        self.elf2hex_cmd = 'elf2hex {0} 4194304 dut.elf 2147483648 > code.mem;'.format(str(int(self.xlen/8)))
        self.objdump_cmd = 'riscv{0}-unknown-elf-objdump -D dut.elf > dut.disass;'.format(self.xlen)
        self.sim_cmd = './chromite_core'
        self.sim_args = '+rtldump > /dev/null'
        self.sim_path = '/scratch/git-repo/incoresemi/core-generators/chromite/bin/'

        self.work_dir = os.path.abspath(work_dir) + '/'
        self.test_list = load_yaml(test_list)

        self.report_dir = self.work_dir + '/' + self.name + '/'
        # Check if dir exists
        if (os.path.isdir(self.report_dir)):
            logger.debug(self.report_dir + ' Directory exists')
        else:
            os.makedirs(self.report_dir)

        if not os.path.exists(self.sim_path):
            logger.error('Sim binary Path ' + self.sim_path + ' does not exist')
            raise SystemExit

        if not os.path.isfile(self.sim_path + '/' + self.sim_cmd):
            logger.error(self.sim_cmd + ' binary does not exist in ' +
                    self.sim_path)
            raise SystemExit

        if shutil.which('elf2hex') is None:
            logger.error('elf2hex utility not found in $PATH')

    @dut_hookimpl
    def build(self):
        logger.debug('Build Hook')
        make = makeUtil(makefilePath=os.path.join(self.work_dir,"Makefile." +\
            self.name))
        make.makeCommand = 'make -j1'
        self.make_file = os.path.join(self.work_dir, 'Makefile.'+self.name)
        self.test_names = []

        for test,attr in self.test_list.items():
            logger.debug('Creating Make Target for ' + str(test))
            abi         = attr['mabi']
            arch        = attr['march']
            isa         = attr['isa']
            work_dir    = attr['work_dir']
            link_args   = attr['linker_args']
            link_file   = attr['linker_file']
            cc          = attr['cc']
            cc_args     = attr['cc_args']
            asm_file    = attr['asm_file']

            ch_cmd = 'cd {0};'.format(work_dir)
            compile_cmd = '{0} {1} -march={2} -mabi={3} {4} {5} {6}'.format(\
                    cc, cc_args, arch, abi, link_args, link_file, asm_file)
            for x in attr['extra_compile']:
                compile_cmd += ' ' + x
            compile_cmd += ' -o dut.elf;'
            sim_setup = 'ln -f -s ' + self.sim_path+'/* .;'
            post_process_cmd = 'mv rtl.dump dut.dump;'
            target_cmd = ch_cmd + compile_cmd + self.objdump_cmd +\
                    self.elf2hex_cmd + sim_setup + self.sim_cmd + ' ' + \
                    self.sim_args +';'+ post_process_cmd
            make.add_target(target_cmd,test)
            self.test_names.append(test)


    @dut_hookimpl
    def run(self, module_dir):
        logger.debug('Run Hook')
        logger.debug('Module dir: {0}'.format(module_dir))
        pytest_file = module_dir + '/chromite_verilator_plugin/gen_framework.py'
        logger.debug('Pytest file: {0}'.format(pytest_file))

        report_file_name = '{0}/{1}_{2}'.format(
            self.report_dir,
            self.name,
            datetime.datetime.now().strftime("%Y%m%d-%H%M"))

        # TODO Regression list currently removed, check back later
        # TODO The logger doesn't exactly work like in the pytest module
        # pytest.main([pytest_file, '-n={0}'.format(self.jobs), '-k={0}'.format(self.filter), '-v', '--compileconfig={0}'.format(compile_config), '--html=compile.html', '--self-contained-html'])
        # breakpoint()
        pytest.main([
            pytest_file,
            '-n={0}'.format(self.jobs),
            '-k={0}'.format(self.filter),
            '--html={0}.html'.format(self.work_dir+'/'+self.name),
            '--report-log={0}.json'.format(report_file_name),
            '--work_dir={0}'.format(self.work_dir),
            '--make_file={0}'.format(self.make_file),
            '--key_list={0}'.format(self.test_names),
            '--log-cli-level=DEBUG',
            '-o log_cli=true',
        ])
        # , '--regress_list={0}'.format(self.regress_list), '-v', '--compile_config={0}'.format(compile_config),
        return report_file_name

    @dut_hookimpl
    def post_run(self):
        # TODO:NEEL: The following is no longer required.

#        logger.debug('Post Run')
#        log_dir = self.work_dir
#        log_files = glob.glob(log_dir + '*/*dut_rc.dump')
#        logger.debug("Detected Chromite Log Files: {0}".format(log_files))
        return
