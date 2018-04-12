import sys
import os
from pysqlcipher import dbapi2 as sqlite
import traceback

def main():
    argv = sys.argv
    if len(argv) != 4:
        print 'usage: python desql.py encrypted_file password decrypted_file'
        return
    encrypted_file = argv[1]
    password = argv[2]
    decrypted_file = argv[3]
    conn = sqlite.connect(encrypted_file)
    c = conn.cursor()
    try:
        c.execute("PRAGMA key = '" + password + "';")
        c.execute("PRAGMA cipher_use_hmac = OFF;")
        c.execute("PRAGMA cipher_page_size = 1024;")
        c.execute("PRAGMA kdf_iter = 4000;")
        c.execute("ATTACH DATABASE '" + decrypted_file + "' AS wechatdecrypted KEY '';")
        c.execute( "SELECT sqlcipher_export( 'wechatdecrypted' );" )
        c.execute( "DETACH DATABASE wechatdecrypted;" )
        c.close()
        print 'Decrypt Success!'
    except:
        c.close()
        os.remove(decrypted_file)
        print 'Decrypt Error!'
        print 'Exception:'
        print traceback.format_exc()

if __name__ == '__main__':
    main()