variable "cloud" {
  type        = string
  description = "The cloud you want to use from clouds.yaml"
  sensitive   = false
}

variable "ssh_public_key_path" {
  type = string
  description = "path to public key you would like to add to openstack"
}

variable "kubernetes_count" {
  type = number
  description = "number of kubernetes nodes"
  default = 3
}

variable "kubernetes_image" {
  type = string
  description = "Image name for kubernetes nodes"
  default = "Ubuntu 24.04"
}

variable "kubernetes_flavor" {
  type = string
  description = "Flavor name for kubernetes nodes"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "network_count" {
  type = number
  description = "number of network nodes"
  default = 3
}

variable "network_image" {
  type = string
  description = "Image name for network nodes"
  default = "Ubuntu 24.04"
}

variable "network_flavor" {
  type = string
  description = "Flavor name for network nodes"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "controller_count" {
  type = number
  description = "number of controllers"
  default = 5
}

variable "controller_image" {
  type = string
  description = "Image name for controller"
  default = "Ubuntu 24.04"
}

variable "controller_flavor" {
  type = string
  description = "Flavor name for controller"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "worker_count" {
  type = number
  description = "number of workers"
  default = 4
}

variable "worker_image" {
  type = string
  description = "Image name for workers"
  default = "Ubuntu 24.04"
}

variable "worker_flavor" {
  type = string
  description = "Flavor name for workers"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "compute_count" {
  type = number
  description = "Number of compute nodes"
  default = 2
}

variable "compute_image" {
  type = string
  description = "Image name for compute nodes"
  default = "Ubuntu 24.04"
}

variable "compute_flavor" {
  type = string
  description = "Flavor name for compute nodes"
<<<<<<< Updated upstream
  default = "gp.5.2.8"
=======
  default = "gp.5.4.16"
>>>>>>> Stashed changes
}

variable "storage_count" {
  type = number
  description = "Number of workers that will also have storage volumes."
  default = 3
}

variable "storage_image" {
  type = string
  description = "Image name for storage nodes"
  default = "Ubuntu 24.04"
}

variable "storage_flavor" {
  type = string
  description = "Flavor name for storage nodes"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "ceph_count" {
  type = number
  description = "Number of ceph nodes that will also have storage volumes."
  default = 3
}

variable "ceph_image" {
  type = string
  description = "Image name for ceph nodes"
  default = "Ubuntu 24.04"
}

variable "ceph_flavor" {
  type = string
  description = "Flavor name for ceph nodes"
<<<<<<< Updated upstream
  default = "gp.5.2.6"
=======
  default = "gp.5.2.8"
>>>>>>> Stashed changes
}

variable "bastion_image" {
  type = string
  description = "Image name for bastion node"
  default = "Ubuntu 24.04"
}

variable "bastion_flavor" {
  type = string
  description = "Flavor name for bastion node"
<<<<<<< Updated upstream
  default = "gp.5.4.4"
=======
  default = "gp.5.2.4"
>>>>>>> Stashed changes
}

variable "cluster_name" {
  type = string
  description = "Name of the cluster"
  default = "cluster.local"
}
variable "mlb_vips" {
  type = list(string)
  description = "VIPs to create for Metal LB, should not overlap with subnet allocation pool!"
  default = ["172.31.3.1", "172.31.3.2", "172.31.3.3"]
}
