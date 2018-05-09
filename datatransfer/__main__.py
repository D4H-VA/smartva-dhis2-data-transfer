try:
    from .run import launch
except (ImportError, SystemError):
    from datatransfer.run import launch

if __name__ == '__main__':
    launch()
