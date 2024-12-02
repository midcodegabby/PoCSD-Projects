import pickle, logging
import fsconfig
import xmlrpc.client, socket, time

#### BLOCK LAYER

# global TOTAL_NUM_BLOCKS, BLOCK_SIZE, INODE_SIZE, MAX_NUM_INODES, MAX_FILENAME, INODE_NUMBER_DIRENTRY_SIZE

class DiskBlocks():
    def __init__(self):

        # initialize clientID
        if fsconfig.CID >= 0 and fsconfig.CID < fsconfig.MAX_CLIENTS:
            self.clientID = fsconfig.CID
        else:
            print('Must specify valid cid')
            quit()

        # initialize cache dict: key, value = block number, block contents
        self.cache = {}

        # initialize XMLRPC client connection to raw block server
        if fsconfig.PORT:
            PORT = fsconfig.PORT
        else:
            print('Must specify port number')
            quit()
        server_url = 'http://' + fsconfig.SERVER_ADDRESS + ':' + str(PORT)
        self.block_server = xmlrpc.client.ServerProxy(server_url, use_builtin_types=True)
        socket.setdefaulttimeout(fsconfig.SOCKET_TIMEOUT)

    # Method to check and validate client cache vs server cache
    def CheckAndInvalidateCache(self):
        # get current CID in server; the CID is stored in server_CID[0]
        server_CID = self.Get(fsconfig.TOTAL_NUM_BLOCKS - 2)

        # handle case where cache is valid
        if fsconfig.CID == server_CID[0]:
            return 0

        # handle case where cache is invalid
        else:
            print("CACHE_INVALIDATED")

            # create block to store CID
            new_CID = bytearray(fsconfig.BLOCK_SIZE)
            new_CID[0] = fsconfig.CID

            # store the CID into the server
            self.Put((fsconfig.TOTAL_NUM_BLOCKS - 2), new_CID)

            # invalidate the cache by making it empty
            self.cache = {}

            return 0
        
    # RSM (read and set memory) method: this method returns the data in the lock block, and sets the 
    # lock block (the last block) to 1
    def RSM(self):

        #use atomic RSM on server side
        lock_read = self.block_server.RSM(fsconfig.TOTAL_NUM_BLOCKS - 1)

        return lock_read[0]

    ## Acquire method
    def Acquire(self): 
        # use RSM
        lock = self.RSM()

        # loop until lock[0] is 0 (unlocked)
        while (lock == 1):
            lock = self.RSM()
        
        return 0

    ## Release method
    def Release(self):
        # create a byte array to store the lock (0) in:
        unlock = bytearray(fsconfig.BLOCK_SIZE) 

        self.Put((fsconfig.TOTAL_NUM_BLOCKS - 1), unlock)

        return 0

    ## Put: interface to write a raw block of data to the block indexed by block number
    ## Blocks are padded with zeroes up to BLOCK_SIZE

    def Put(self, block_number, block_data):

        logging.debug(
            'Put: block number ' + str(block_number) + ' len ' + str(len(block_data)) + '\n' + str(block_data.hex()))
        if len(block_data) > fsconfig.BLOCK_SIZE:
            logging.error('Put: Block larger than BLOCK_SIZE: ' + str(len(block_data)))
            quit()

        if block_number in range(0, fsconfig.TOTAL_NUM_BLOCKS):
            # just does the padding with zeros
            putdata = bytearray(block_data.ljust(fsconfig.BLOCK_SIZE, b'\x00'))
            
            # put the data into the cache, but only if it is not the MAX-1 or MAX-2 block
            if block_number < (fsconfig.TOTAL_NUM_BLOCKS - 2):
                self.cache[block_number] = putdata 
            
            # loop for 2 tries: 
            for i in range(2): 
                # implement try/except stuff for at-least-once semantics
                try:
                    ret = self.block_server.Put(block_number, putdata) # RPC
                
                # exception handling for the 5 second socket timout exception:
                except socket.timeout:
                    print("SERVER_TIMED_OUT") # print error message
                    time.sleep(fsconfig.RETRY_INTERVAL) # sleep for RETRY_INTERVAL (10s)

                # handle the case where no timeout occurs:
                else:
                    print("CACHE_WRITE_THROUGH " + str(block_number)) 
                    return 0

            if ret == -1:
                logging.error('Put: Server returns error')
                quit()
        else:
            logging.error('Put: Block out of range: ' + str(block_number))
            quit()

    ## Get (cached and server): interface to read a raw block of data from block indexed by block number
    ## Equivalent to the textbook's BLOCK_NUMBER_TO_BLOCK(b)
    def Get(self, block_number):

        logging.debug('Get: ' + str(block_number))
        if block_number in range(0, fsconfig.TOTAL_NUM_BLOCKS):
            
            # check cache first and handle cache miss/hit with try/except/else
            try:
                cache_data = self.cache[block_number]
            
            # if the block_number is not in the cache
            except KeyError:
                print("CACHE_MISS " + str(block_number))

                # get the block from the server using RPC
                # loop for 2 tries: 
                for i in range(2): 
                    # implement try/except stuff for at-least-once semantics
                    try:
                        server_data = self.block_server.Get(block_number)
                    
                    # exception handling for the 5 second socket timout exception:
                    except socket.timeout:
                        print("SERVER_TIMED_OUT") #print error message
                        time.sleep(fsconfig.RETRY_INTERVAL) # sleep for RETRY_INTERVAL (10s)
                    
                    # handle the case where no timeout occurs:
                    else:
                        if block_number < (fsconfig.TOTAL_NUM_BLOCKS - 2):
                            self.cache[block_number] = bytearray(server_data)   # update the cache
                            return bytearray(server_data)
                        
                        # else statements prevents caching the CID or Lock
                        else:
                            return bytearray(server_data)

            # if the block_number is in the cache   
            else:
                print("CACHE_HIT " + str(block_number))

                return bytearray(cache_data)

        logging.error('DiskBlocks::Get: Block number larger than TOTAL_NUM_BLOCKS: ' + str(block_number))
        quit()


    ## Serializes and saves the DiskBlocks block[] data structure to a "dump" file on your disk

    def DumpToDisk(self, filename):

        logging.info("DiskBlocks::DumpToDisk: Dumping pickled blocks to file " + filename)
        file = open(filename,'wb')
        file_system_constants = "BS_" + str(fsconfig.BLOCK_SIZE) + "_NB_" + str(fsconfig.TOTAL_NUM_BLOCKS) + "_IS_" + str(fsconfig.INODE_SIZE) \
                            + "_MI_" + str(fsconfig.MAX_NUM_INODES) + "_MF_" + str(fsconfig.MAX_FILENAME) + "_IDS_" + str(fsconfig.INODE_NUMBER_DIRENTRY_SIZE)
        pickle.dump(file_system_constants, file)
        pickle.dump(self.block, file)

        file.close()

    ## Loads DiskBlocks block[] data structure from a "dump" file on your disk

    def LoadFromDump(self, filename):

        logging.info("DiskBlocks::LoadFromDump: Reading blocks from pickled file " + filename)
        file = open(filename,'rb')
        file_system_constants = "BS_" + str(fsconfig.BLOCK_SIZE) + "_NB_" + str(fsconfig.TOTAL_NUM_BLOCKS) + "_IS_" + str(fsconfig.INODE_SIZE) \
                            + "_MI_" + str(fsconfig.MAX_NUM_INODES) + "_MF_" + str(fsconfig.MAX_FILENAME) + "_IDS_" + str(fsconfig.INODE_NUMBER_DIRENTRY_SIZE)

        try:
            read_file_system_constants = pickle.load(file)
            if file_system_constants != read_file_system_constants:
                print('DiskBlocks::LoadFromDump Error: File System constants of File :' + read_file_system_constants + ' do not match with current file system constants :' + file_system_constants)
                return -1
            block = pickle.load(file)
            for i in range(0, fsconfig.TOTAL_NUM_BLOCKS):
                self.Put(i,block[i])
            return 0
        except TypeError:
            print("DiskBlocks::LoadFromDump: Error: File not in proper format, encountered type error ")
            return -1
        except EOFError:
            print("DiskBlocks::LoadFromDump: Error: File not in proper format, encountered EOFError error ")
            return -1
        finally:
            file.close()


## Prints to screen block contents, from min to max

    def PrintBlocks(self,tag,min,max):
        print ('#### Raw disk blocks: ' + tag)
        for i in range(min,max):
            print ('Block [' + str(i) + '] : ' + str((self.Get(i)).hex()))
