interprets certain commonly used structures in the values file for a Helm Release as referring to images, at least an image key needs to be specified. The following are understood (showing just the values section):

values:
  image: repo/image:version

values:
  image: repo/image
  tag: version

values:
  registry: docker.io
  image: repo/image
  tag: version

values:
  image:
    repository: repo/image
    tag: version

values:
  image:
    registry: docker.io
    repository: repo/image
    tag: version

