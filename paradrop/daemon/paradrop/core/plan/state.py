###################################################################
# Copyright 2013-2016 All Rights Reserved
# Authors: The Paradrop Team
###################################################################

from paradrop.base.output import out
from paradrop.base.pdutils import jsonPretty
from paradrop.base import settings
from paradrop.core.chute.chute import Chute
from paradrop.core.config import state
from paradrop.core.container import dockerapi

from . import plangraph


def generatePlans(update):
    """
        This function looks at a diff of the current Chute (in @chuteStor) and the @newChute,
        then adds Plan() calls to make the Chute match the @newChute.

        Returns:
            True: abort the plan generation process
    """
    out.verbose("%r\n" % (update))

    if update.updateType in ['create', 'update']:
        update.plans.addPlans(plangraph.STATE_BUILD_IMAGE,
                (dockerapi.buildImage, ),
                (dockerapi.removeNewImage, ))

    # If this chute is new (no old version)
    if(update.old is None):
        out.verbose('new chute\n')

        # If it's a stop, start, delete, or restart command go ahead and fail right now since we don't have a record of it
        if update.updateType in ['stop', 'start', 'delete', 'restart']:
            update.failure = "No chute found with id: " + update.name
            return True

        # If we are now running then everything has to be setup for the first time
        if update.new.state == Chute.STATE_RUNNING:
            update.plans.addPlans(plangraph.STATE_CALL_START,
                    (dockerapi.startChute, ),
                    (dockerapi.removeNewContainer, ))

        # Check if the state is invalid, we should return bad things in this case (don't do anything)
        elif(update.new.state == Chute.STATE_INVALID):
            if(settings.DEBUG_MODE):
                update.responses.append('Chute state is invalid')
            return True

    # Not a new chute
    else:
        if update.updateType == 'start':
            if update.old.state == Chute.STATE_RUNNING:
                update.failure = update.name + " already running."
                return True
            update.plans.addPlans(plangraph.STATE_CALL_START, (dockerapi.restartChute,))
        elif update.updateType == 'restart':
            update.plans.addPlans(plangraph.STATE_CALL_STOP,
                    (dockerapi.removeOldContainer, ),
                    (dockerapi.startOldContainer, ))
            update.plans.addPlans(plangraph.STATE_CALL_START,
                    (dockerapi.startChute, ),
                    (dockerapi.removeNewContainer, ))
        elif update.updateType == 'create':
            update.failure = update.name + " already exists on this device."
            return True
        elif update.updateType == 'update':
            if update.new.version == update.old.version:
                update.failure = "Version {} already exists on this device.".format(update.new.version)
                return True
            elif (update.new.version < update.old.version) and settings.REJECT_DOWNGRADE:
                update.failure = "A newer version ({}) already exists on this device.".format(update.old.version)
                return True
            else:
                update.plans.addPlans(plangraph.STATE_CALL_STOP,
                        (dockerapi.removeOldContainer, ),
                        (dockerapi.startOldContainer, ))
                update.plans.addPlans(plangraph.STATE_CALL_START,
                        (dockerapi.startChute, ),
                        (dockerapi.removeNewContainer, ))
                update.plans.addPlans(plangraph.STATE_CALL_CLEANUP,
                        (dockerapi.removeOldImage, ))
        elif update.new.state == Chute.STATE_STOPPED:
            if update.updateType == 'delete':
                update.plans.addPlans(plangraph.STATE_CALL_STOP, (dockerapi.removeChute,))
            if update.updateType == 'stop':
                if update.old.state == Chute.STATE_STOPPED:
                    update.failure = update.name + " already stopped."
                    return True
                update.plans.addPlans(plangraph.STATE_CALL_STOP, (dockerapi.stopChute,))


    if update.old is not None and update.old.isRunning():
        update.plans.addPlans(plangraph.STATE_NET_STOP,
                (dockerapi.cleanup_net_interfaces,),
                (dockerapi.setup_net_interfaces,))

    if update.new.isRunning():
        update.plans.addPlans(plangraph.STATE_NET_START,
                (dockerapi.setup_net_interfaces,),
                (dockerapi.cleanup_net_interfaces,))

    # Save the chute to the chutestorage.
    update.plans.addPlans(plangraph.STATE_SAVE_CHUTE,
            (state.saveChute,),
            (state.revertChute,))

    return None
