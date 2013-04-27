#!/usr/bin/env python

# Name: 
#   dism-this.py
# Version: 
#    0.3
# New:
#   0.2 - added support for export/carving shellcode
#   0.3 - fixed segment string parsing bug. Reported by Lenny Zeltser.  
# Description: 
#    dism-this.py is a script that analyzes data for the possible detection of shellcode or instructions.      
# Author
#    alexander<dot>hanel<at>gmail<dot>com

import re
import sys
from optparse import OptionParser

class CKASM():
    def __init__(self):
        self.brRegex = re.compile(r'\[.+?\]')
        self.registers = ['eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp', 'ebp', 'ax', 'bx', 'cx', 'dx', 'ah', 'al', 'bh', 'bp', 'bl', 'ch', 'cl', 'dh', 'dl', 'di', 'si', 'sp', 'ip']
        self.popMnem = ['push', 'call', 'mov', 'pop', 'add', 'inc', 'and', 'movzx', 'cdq', 'idiv', 'shr', 'test', 'or', 'xor', 'sub', 'jz', 'retn', 'jnz', 'jmp', 'jnb', 'cmp']
        self.segment = [ 'ds', 'cs', 'ss', ' es', 'gs', 'fs']
        self.segmentCount = 0 
        self.errorCount = 0
        self.skip =  None
        self.count = None 
        self.buffer = None
        self.ascii = False
        self.export = False
        self.exportFile = None 
        self.verbose = False
        self.fhandle = None
        self.parser = None
        self.callParser()
        self.checkFileArgs()
        self.getBuffer()
        self.asciiBlob()
        self._export()
        self.errorStaticCount = 0
        self.errorStatic = []
        self.errorInvalidInstCount = 0
        self.errorInvalidInst = []
        self.outcastInstr = 0

    def _export(self):
        if self.export == False:
            return     
        f = open(self.exportFile, 'wb')
        f.write(self.buffer)
        f.close()
        sys.exit(0)
        
    def dis(self, buff):
        'disassembles buffer using pydasm, returns assembly in buffer'
        try:
            import pydasm
        except ImportError:
            print "Error: Pydasm Can Not be Found"
            sys.exit()
        offset = 0
        outDis = []
        while offset < len(buff):
            i = pydasm.get_instruction(buff[offset:],pydasm.MODE_32)
            tmp = pydasm.get_instruction_string(i,pydasm.FORMAT_INTEL,offset)
            outDis.append(tmp)
            if not i:
                return outDis
            offset +=  i.length
        return outDis

    def callParser(self):
        'parses the command line arguments'
        self.parser = OptionParser()
        usage = 'usage: %prog [options] <data.file>'
        self.parser = OptionParser(usage=usage)
        # command options
        self.parser.add_option('-v', '--verbose', action='store_true', dest='verbose', help="print disassembly")
        self.parser.add_option('-s', '--skip', type="int", dest='skip', help='skip n input bytes')
        self.parser.add_option('-c' , '--count', type="int", dest='count', help='disassembly only n input blocks')
        self.parser.add_option('-a', '--ascii_blob', action='store_true', dest='ascii', help='disassembly ascii blob')
        self.parser.add_option('-e', '--export',  type='string', dest='export', help='export buffer to file name')
        (options, args) = self.parser.parse_args()
        # Assigns passed variables 
        if options.verbose == True:
            self.verbose = True
        if options.skip != None:
            self.skip = options.skip
        if options.count != None:
            self.count = options.count
        if options.ascii != None:
            self.ascii = options.ascii
        if options.export != None:
            self.export = True
            self.exportFile = options.export
        
    def analyzeInstr(self, line):
        'add instruction analysis here' 
        if None == line:
            return
        elif '??' in line:
            self.errorInvalidInstCount += 1
            self.errorInvalidInst.append(line)
            return 
        elif '[' in line and ']' in line:
            if self.staticOffset(line) != None:
                self.errorStaticCount += 1
                self.errorStatic.append(line)
                return 
        self.segmentCheck(line)
        self.outcast(line)
        return 
        
    def checkOffsetBounds(self, line):
        if  self.getOffset(line) > 0xfffff and line != None:
            print "Invalid: Offset %s" % line
            
    def staticOffset(self, line):
        value = re.search(self.brRegex, line).group(0)[1:-1]
        try:
            tmp = int(value,16)
            return tmp 
        except:
            return None 

    def segmentCheck(self,line):
        for seg in self.segment:
	    segs = str(seg + ':')
            if segs in line:
                self.segmentCount += 1
                
    def outcast(self,line):
        b = False
        for mnem in self.popMnem:
            if mnem in line[0:5]:
                return
            else:
                b = False
        if b == False:
            self.outcastInstr += 1
        
    def checkFileArgs(self):
        'janky way for checking file arguments'
        if len(sys.argv) == 1:
            self.parser.print_help()
            sys.exit()
        else:
            if sys.argv[len(sys.argv)-1] == self.exportFile:
                print "ERROR: Could not access file passed as argument" 
                sys.exit()
            try:
                self.fhandle = open(sys.argv[len(sys.argv)-1], 'rb')
            except:
                print "ERROR: Could not access file passed as argument" 
                sys.exit()
        pass
        
    def asciiBlob(self):
        'converts ascii blobs to binary two bytes at a time'
        if self.ascii == False:
            return 
        from StringIO import StringIO
        tmpBuff = StringIO(self.buffer)
        buff = ''
        b = tmpBuff.read(2)
        while b != '':
            try:
                buff = buff + chr(int(b,16))
                b = tmpBuff.read(2)
            except ValueError:
                break
        self.buffer = buff
        
    def getBuffer(self):
        'checks the skip and count contents then reads the data to a buffer'
        if self.skip != None:
            self.fhandle.seek(self.skip)
        if self.count != None:
            self.buffer = self.fhandle.read(int(self.count))
            return
        self.buffer = self.fhandle.read()
        return 
        
    def start(self):
        'disneyland'
        disO = self.dis(self.buffer)
        for assemblyLine in list(disO):
            self.analyzeInstr(assemblyLine)
        if self.verbose == True:
            self.verbosed(disO)
        self.output(disO)
            
    def output(self,disO):
        'print output of analysis'
        print "Analysis:"
        print "\tInfo: Instructions Disassembled Count %s" % len(disO)
        print "\tError: Invalid Disassembly Count %s" % self.errorInvalidInstCount
        print "\t\t* Example: ?? jna 0x129"	
        print "\tInvalid: Static Offset Count %s " % self.errorStaticCount
        print "\t\t* Example: sub [0xd218000a], ecx"	
        print "\tInvalid: Segment Register Use Count %s " % self.segmentCount
        print "\t\t* Example: fs daa"
        print "\tAnomaly: Infrequent Instruction Use Count %s " % self.outcastInstr
        print "\t\t* Example: arpl [ebp+ecx+0xa],bp"
        print

    def verbosed(self, disO):
        'print disassembly'
        print 'Disassembly:'
        for assemblyLine in list(disO):
            print '\t' + assemblyLine
        print 

def main():
    ck = CKASM()
    ck.start()

if __name__ == "__main__":
    main()


'''
# Random Notes..

# concordance...

instr = []
ea = ScreenEA()
for funcea in Functions(SegStart(ea), SegEnd(ea)):
	E = list(FuncItems(ea))
	for e in E:
		instr.append(GetMnem(e))

count = {}
for mnem in instr:
	if mnem in count:
		count[mnem] += 1
	else:
		count[mnem]  = 1
		

popMnem = sorted(count, key = count.get, reverse = True)

print popMnem[:35]


'''
