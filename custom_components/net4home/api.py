#################################################################################
sub N4HBUS_DoInit($) {
#################################################################################

	my $hash = shift;
	my $name = $hash->{NAME};
	delete $hash->{HANDLE}; 

	# set OBJ and MI if not defined as attributes
	if (!defined($hash->{OBJADR}) ) {
		$attr{$name}{OBJADR} = 32700;
	}
		
	if (!defined($hash->{MI}) ) {
		$attr{$name}{MI}  = 65281;
	}

	my $sendmsg = "190000000002ac0f400a000002bc02404600000487000000c000000200";
	DevIo_SimpleWrite($hash, $sendmsg, 1);
	return undef;
}
