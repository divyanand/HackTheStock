def func():
    print("Name: {}".format(__name__))
    print("File: {}".format(__file__))
    print("Doc : {}".format(__doc__))
    print("Impo: {}".format(__import__))
    print("Pkg : {}".format(__package__))
    print("funname : {}".format(self.__name__))

func()