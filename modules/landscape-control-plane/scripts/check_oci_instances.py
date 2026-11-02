import oci

for profile in ["atius1", "atius2", "atius3", "atius4"]:
    try:
        config = oci.config.from_file(profile_name=profile)
        compute = oci.core.ComputeClient(config)
        network = oci.core.VirtualNetworkClient(config)
        instances = compute.list_instances(config["tenancy"]).data
        print(f"=== PROFILE {profile} ===")
        for i in instances:
            vnic_attachments = compute.list_vnic_attachments(config["tenancy"], instance_id=i.id).data
            ips = []
            for va in vnic_attachments:
                try:
                    vnic = network.get_vnic(va.vnic_id).data
                    ips.append((vnic.private_ip, vnic.public_ip))
                except Exception:
                    pass
            print(f"  HOST: {i.display_name} | STATE: {i.lifecycle_state} | IPS: {ips}")
    except Exception as e:
        print(f"PROFILE {profile} ERROR: {e}")
