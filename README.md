# hks_pynetwork
A Python library is built for communication between objects in internal or external programs.

# How to build
We are assuming that your code is running on the Python 3.7.1. If you meet any problems, even if with other versions, let [create an issue](https://github.com/huykingsofm/hks_pylib/issues) to notify us. We will solve them as quick as possible.  

## Create Virtual Enviroment (optional but IMPORTANT)
*If you had your own virtual enviroment, you can ignore this step.* 

You should create a virtual enviroment to avoid conflicting with other applications on your machine when installing our module. The virtual enviroment should be installed with [Python 3.7.1](https://www.python.org/downloads/release/python-371/) (you can use other Python versions but we can't ensure that unexpected errors will not appear suddenly).  
I highly recommend you to use [Anaconda](https://www.anaconda.com/products/individual) because of its utilities. The command of creating virtual enviroment in Anaconda is:
```bash
$ conda create -n your_venv_name python=3.7.1
$ conda activate your_venv_name
(your_venv_name) $ _ 
```

Or use `Python venv`:
```bash
$ python -m venv path/to/your/venv
$ path/to/your/venv/Scripts/activate.bat
(your_venv_name) $ _
```

## Method 1: Install the most stable version
```bash
(your_venv_name) $ pip install hks_pynetwork
```

## Method 2: Install the newest version

```bash
(your_venv_name) $ pip install -r requirements.txt
(your_venv_name) $ pip install -e .
```

# How to use
Just use `import` statement and enjoy it. We will write documentations and tutorials as soon as possible so that you can understand our library easier.

```python
from hks_pynetwork import internal
from hks_pynetwork import external
```
