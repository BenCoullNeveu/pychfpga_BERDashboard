import socket
import asyncio
import netifaces

async def ping_async(addr, timeout=0.3):
    """
    Establish a TCP connection with `addr`  at and return the interface and local port used for the connection.

    Parameters:
        addr ((str, int) tuple): Address and port to which a TCP connection is made
        timeout (fload): Time to wait before giving up on the connection

    Return:
        An (interface_address, local_port) if the connection is successful, None otherwise.

    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    loop = asyncio.get_event_loop()
    try:
        await loop.sock_connect(s, addr)
        if_addr = s.getsockname()
        s.close()
    except (socket.timeout, Exception) as e:
        # self.log.warn(f'Could not establish a TCP connection with {addr[0]}:{addr[1]}. Error is:\n {e}')
        if_addr = None

    return if_addr


async def ping_sources_async(port_map):
    src_addrs = [tuple(src) for port_info in port_map
                 for src in port_info['sources']]
    src_if_addrs = await asyncio.gather(*[ping_async(src) for src in src_addrs])
    return dict(zip(src_addrs, src_if_addrs))