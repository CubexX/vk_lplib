from setuptools import setup

setup(name='vk_lplib',
      version='0.2',
      description='VK Long Poll lib',
      url='https://github.com/stroum/vk_lplib',
      author='stroum',
      author_email='rapperson1@gmail.com',
      license='MIT',
      install_requires=[
          'requests',
          'gevent'
      ],
      packages=['vk_lplib'],
      zip_safe=False)
