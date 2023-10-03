import psutil
import logging


def check_udp_buffers_size():
    buff_config = list()
    with open("/proc/sys/net/core/rmem_max") as file:
        buff_config.append(int(file.readline()))
    with open("/proc/sys/net/core/rmem_default") as file:
        buff_config.append(int(file.readline()))
    with open("/proc/sys/net/ipv4/udp_mem") as file:
        for val in file.readline().split():
            buff_config.append(int(val))
    with open("/proc/sys/net/ipv4/udp_rmem_min") as file:
        buff_config.append(int(file.readline()))

    if any(val < 26214400 for val in buff_config):
        raise RuntimeError("The UDP buffers' memory parameters (net.core.rmem_max, net.core.rmem_default, "
                           "net.ipv4.udp_mem, net.ipv4.udp_rmem_min) are too low. Increase them to at least 26214400 "
                           "bytes. You can do it by running:\n"
                           "\tsudo sysctl -w net.core.rmem_max=26214400\n"
                           "\tsudo sysctl -w net.core.rmem_default=26214400\n"
                           "\tsudo sysctl -w net.ipv4.udp_mem='26214400 26214400 26214400'\n"
                           "\tsudo sysctl -w net.ipv4.udp_rmem_min=26214400")


def check_mtu_size(logger: logging.Logger):
    net_stats = psutil.net_if_stats()
    eth_keys = [key for key in net_stats.keys() if key.startswith("enp")]
    if all(net_stats[key].mtu < 9000 for key in eth_keys):
        logger.warning("Cannot find an ethernet connection with MTU size >= 9000 bytes. Please make sure you "
                       "have a connection with MTU size set to 9000. Otherwise some packages may be lost.")

