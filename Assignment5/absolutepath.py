import fsconfig
import logging
from block import *
from inode import *
from inodenumber import *
from filename import *

## This class implements methods for absolute path layer

class AbsolutePathName():
  def __init__(self, FileNameObject):
    self.FileNameObject = FileNameObject

  def PathToInodeNumber(self, path, dir):

    logging.debug("AbsolutePathName::PathToInodeNumber: path: " + str(path) + ", dir: " + str(dir))

    if "/" in path:
      split_path = path.split("/")
      first = split_path[0]
      del split_path[0]
      rest = "/".join(split_path)
      logging.debug("AbsolutePathName::PathToInodeNumber: first: " + str(first) + ", rest: " + str(rest))
      d = self.FileNameObject.Lookup(first, dir)
      if d == -1:
        return -1
      return self.PathToInodeNumber(rest, d)
    else:
      return self.FileNameObject.Lookup(path, dir)

  def PathNameToInodeNumber(self, path, cwd):
    # resolves soft links; see textbook p. 105

    logging.debug ("AbsolutePathName::PathNameToInodeNumber: path: " + str(path) + ", cwd: " + str(cwd))

    i = self.GeneralPathToInodeNumber(path, cwd)
    lookedup_inode = InodeNumber(i)
    lookedup_inode.InodeNumberToInode(self.FileNameObject.RawBlocks)

    if lookedup_inode.inode.type == fsconfig.INODE_TYPE_SYM:
      logging.debug ("AbsolutePathName::PathNameToInodeNumber: inode is symlink: " + str(i))

      # read block with target string from RawBlocks
      block_number = lookedup_inode.inode.block_numbers[0]
      block = self.FileNameObject.RawBlocks.Get(block_number)

      # extract slice with length of target string
      target_slice = block[0:lookedup_inode.inode.size]
      rest = target_slice.decode()
      logging.debug ("AbsolutePathName::PathNameToInodeNumber: rest: " + rest)
      i = self.GeneralPathToInodeNumber(rest, cwd)

      return i

  def GeneralPathToInodeNumber(self, path, cwd):

    logging.debug ("AbsolutePathName::GeneralPathToInodeNumber: path: " + str(path) + ", cwd: " + str(cwd))

    if path[0] == "/":
      if len(path) == 1: # special case: root
        logging.debug ("AbsolutePathName::GeneralPathToInodeNumber: returning root inode 0")
        return 0
      cut_path = path[1:len(path)]
      logging.debug ("AbsolutePathName::GeneralPathToInodeNumber: cut_path: " + str(cut_path))
      return self.PathToInodeNumber(cut_path,0)
    else:
      return self.PathToInodeNumber(path,cwd)

  ########################################################################################

  #Implemented methods
  #Creates hard link with title [name] in current directory, whose inode is [cwd] 
  #Params:
    #name - name of link to be created in directory
    #target - path of the target inode to be linked to
  def Link(self, target, name, cwd):

      target_inode_num = self.GeneralPathToInodeNumber(target, cwd)
      link_inode_num = self.GeneralPathToInodeNumber(name, cwd)

      if target_inode_num == -1:
        return "ERROR_LINK_TARGET_DOESNOT_EXIST"

      elif link_inode_num != -1:
        return "ERROR_LINK_ALREADY_EXISTS"
      
      else:
        #Goal 1: create new directory entry [name | inode_num] in the current directory; inode_num = cwd
        available_index = self.FileNameObject.FindAvailableFileEntry(cwd) #get available index in cwd

        if available_index == -1:
          return "ERROR_LINK_DATA_BLOCK_NOT_AVAILABLE"
          
        else:
          #create inode object referring to cwd
          cwd_inode = InodeNumber(cwd) #create InodeNumber object for current directory
          cwd_inode.InodeNumberToInode(self.FileNameObject.RawBlocks) #populate inode object with its raw blocks

          #create inode object referring to target inode
          target_inode = InodeNumber(target_inode_num) #create InodeNumber object for target link
          target_inode.InodeNumberToInode(self.FileNameObject.RawBlocks) #populate inode object with its raw blocks

          if cwd_inode.inode.type != fsconfig.INODE_TYPE_DIR:
            return "ERROR_LINK_NOT_DIRECTORY"
        
          elif target_inode.inode.type != fsconfig.INODE_TYPE_FILE:
            return "ERROR_LINK_TARGET_NOT_FILE"

          else:
            self.FileNameObject.InsertFilenameInodeNumber(cwd_inode, name, target_inode_num) #create dir entry for hard link
            
            #Goal 2: increment refcnt of link_inode and cwd_inode
            cwd_inode.inode.refcnt += 1
            target_inode.inode.refcnt +=1

            #write back inode values to their blocks:
            cwd_inode.StoreInode(self.FileNameObject.RawBlocks)
            target_inode.StoreInode(self.FileNameObject.RawBlocks)

      return 0

      
  #Creates soft link with title [name] in current directory, whose inode is [cwd] 
  #Params:
    #name - name of link to be created in directory
    #target - path of the target inode to be linked to
  def Symlink(self, target, name, cwd):

      target_inode_num = self.GeneralPathToInodeNumber(target, cwd)
      link_inode_num = self.GeneralPathToInodeNumber(name, cwd)

      if target_inode_num == -1:
        return "ERROR_SYMLINK_TARGET_DOESNOT_EXIST"

      elif link_inode_num != -1:
        return "ERROR_SYMLINK_ALREADY_EXISTS"

      elif len(target) > fsconfig.BLOCK_SIZE:
        return "ERROR_SYMLINK_TARGET_EXCEEDS_BLOCK_SIZE" 

      else:
        #Goal 1: create new directory entry [name | inode_num] in the current directory; inode_num = new inode num 
        available_index = self.FileNameObject.FindAvailableFileEntry(cwd) #get available index in cwd

        if available_index == -1:
          return "ERROR_SYMLINK_DATA_BLOCK_NOT_AVAILABLE"
          
        else:
          #check if there is an available inode to put symlink in
          available_inode_num = self.FileNameObject.FindAvailableInode()

          if available_inode_num == -1:
            return "ERROR_SYMLINK_INODE_NOT_AVAILABLE"
          
          else:
            #create inode object referring to current working directory inode
            cwd_inode = InodeNumber(cwd) #create InodeNumber object for current directory
            cwd_inode.InodeNumberToInode(self.FileNameObject.RawBlocks) #populate inode object with its raw blocks

            #create inode object referring to symlink inode
            symlink_inode = InodeNumber(available_inode_num) #create InodeNumber object for symlink inode
            #symlink_inode.InodeNumberToInode(self.FileNameObject.RawBlocks) #populate inode object with its raw blocks

            if cwd_inode.inode.type != fsconfig.INODE_TYPE_DIR:
              return "ERROR_SYMLINK_NOT_DIRECTORY"

            else:
              self.FileNameObject.InsertFilenameInodeNumber(cwd_inode, name, available_inode_num) #create dir entry for symlink

              available_block_num = self.FileNameObject.AllocateDataBlock() #init a block to store the symlink's target's name
            
              #Goal 2: initialize symlink_inode to have type INODE_TYPE_SYM, block_numbers[0] = available_block, and refcnt = 1
              symlink_inode.inode.type = fsconfig.INODE_TYPE_SYM
              symlink_inode.inode.refcnt = 1
              symlink_inode.inode.block_numbers[0] = available_block_num
              symlink_inode.inode.size = len(name)

              #Goal 2.5: store "target" to available_block
              targetbyte = bytearray(target, "utf-8")
              block = bytearray(targetbyte.ljust(fsconfig.MAX_FILENAME, b'\x00'))
              self.FileNameObject.RawBlocks.Put(available_block_num, block)

              #Goal 3: increment refcnt of symlink_inode and cwd_inode
              cwd_inode.inode.refcnt += 1
              symlink_inode.inode.refcnt +=1

              #write back inode values to their blocks:
              cwd_inode.StoreInode(self.FileNameObject.RawBlocks)
              symlink_inode.StoreInode(self.FileNameObject.RawBlocks)

      return 0

      




