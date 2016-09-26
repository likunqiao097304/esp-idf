import time

from NativeLog import NativeLog
from TCAction import TCActionBase
from comm.NIC import Adapter

WARNING_COUNT = 2


class PingStress(TCActionBase.CommonTCActionBase):

    def __init__(self, name, test_env, cmd_set, timeout=30, log_path=TCActionBase.LOG_PATH):
        TCActionBase.CommonTCActionBase.__init__(self, name, test_env, cmd_set=cmd_set,
                                                 timeout=timeout, log_path=log_path)
        self.adapter = None
        self.target_mode = "STA"
        # load param from excel
        for i in range(1, len(cmd_set)):
            if cmd_set[i][0] != "dummy":
                cmd_string = "self." + cmd_set[i][0]
                exec cmd_string
        self.result_cntx = TCActionBase.ResultCheckContext(self, test_env, self.tc_name)
        pass

    def cleanup(self):
        self.adapter.close()
        del self.adapter

    def execute(self):
        TCActionBase.TCActionBase.execute(self)
        self.result_cntx.start()

        try:
            # configurable params
            test_time = self.test_time * 60
            # ping data len
            ping_len = self.ping_len
            # test frequency min should be 0.1s, otherwise reply could be missed
            test_freq = self.test_freq if self.test_freq > 0.1 else 0.1
            # target mode
            target_mode = self.target_mode
            # configurable params
        except StandardError, e:
            NativeLog.add_trace_critical("Error configuration for PingStress script, error is %s" % e)
            raise StandardError("Error configuration")

        if target_mode == "STA":
            target_ip = self.get_parameter("target_ip")
            target_mac = self.get_parameter("target_mac")
            pc_mac = self.get_parameter("pc_nic_mac")
            pc_nic_name = self.get_parameter("pc_nic")
        elif target_mode == "SoftAP":
            target_ip = self.get_parameter("target_ap_ip")
            target_mac = self.get_parameter("target_ap_mac")
            pc_mac = self.get_parameter("pc_wifi_nic_mac")
            pc_nic_name = self.get_parameter("pc_wifi_nic")
        else:
            raise StandardError("Unsupported target mode: %s" % target_mode)

        time_start = time.time()
        # open device
        self.adapter = Adapter.Adapter(pc_nic_name, "capture+send")

        ret = self.adapter.set_filter("icmp[icmpcode]=icmp-echoreply and ether src %s and ether dst %s"
                                      % (target_mac, pc_mac))
        if ret != "LIBPCAP_SUCCEED":
            NativeLog.add_trace_critical("PING Stress test error: %s" % ret)
            return

        ret = self.adapter.start_capture()
        if ret != "LIBPCAP_SUCCEED":
            NativeLog.add_trace_critical("PING Stress test error: %s" % ret)
            return

        total_test_count = total_fail_count = successive_fail_count = most_successive_fail_count = 0

        while (time.time() - time_start) < test_time:

            ping_pdu = self.adapter.create_pdu("ICMP", self.adapter.create_payload("A" * ping_len),
                                               icmp_type="echo-request", ipv4_protocol="ICMP",
                                               ipv4_dst_ip=target_ip, ethernet_dst_addr=target_mac)
            # send ping req
            ret = self.adapter.ether_send(ping_pdu.to_bytes())
            if ret != "LIBNET_SUCCEED":
                NativeLog.add_prompt_trace("libnet send fail, %s" % ret)
                continue
            total_test_count += 1
            # wait for reply
            time.sleep(test_freq)
            # should get one ping reply
            pdu_list = self.adapter.get_packets()

            if len(pdu_list) == 0:
                # failed to get ping reply
                total_fail_count += 1
                successive_fail_count += 1
                if successive_fail_count > WARNING_COUNT:
                    NativeLog.add_trace_critical("Ping Fail: successive fail %u times, total tested %u times"
                                                 % (successive_fail_count, total_test_count))
                pass
            else:
                most_successive_fail_count = most_successive_fail_count \
                    if most_successive_fail_count > successive_fail_count \
                    else successive_fail_count
                successive_fail_count = 0
                pass
            pass
        NativeLog.add_trace_critical("Ping stress test, total %s times, failed %s times, most successive fail count %s"
                                     % (total_test_count, total_fail_count, most_successive_fail_count))
        self.result_cntx.set_result("Succeed")
        # finally, execute done

    def result_check(self, port_name, data):
        TCActionBase.CommonTCActionBase.result_check(self, port_name, data)
        self.result_cntx.append_data(port_name, data)


def main():
    pass

if __name__ == '__main__':
    main()
